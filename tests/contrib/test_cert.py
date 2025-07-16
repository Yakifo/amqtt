import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from unittest.mock import MagicMock

from OpenSSL import crypto

import pytest

from amqtt.broker import BrokerContext, Broker
from amqtt.client import MQTTClient
from amqtt.contrib.cert import CertificateAuthPlugin
from amqtt.scripts.server_creds import server_creds as get_server_creds
from amqtt.scripts.device_creds import device_creds as get_device_creds
from amqtt.scripts.ca_creds import ca_creds as get_ca_creds
from amqtt.session import Session

logger = logging.getLogger(__name__)

@pytest.fixture
def temp_directory():
    temp_dir = Path(tempfile.mkdtemp(prefix="amqtt-test-"))
    yield temp_dir
    logger.critical(temp_dir)
    # shutil.rmtree(temp_dir)

@pytest.fixture
def ca_creds(temp_directory):

    get_ca_creds(country='US', state="NY", locality="NYC", org_name="aMQTT", cn="aMQTT", output_dir=str(temp_directory))

    ca_key = temp_directory / "ca.key"
    ca_crt = temp_directory / "ca.crt"
    return ca_key, ca_crt

@pytest.fixture
def server_creds(ca_creds, temp_directory):
    ca_key = temp_directory / "ca.key"
    ca_crt = temp_directory / "ca.crt"
    get_server_creds(country='US', org_name='aMQTT', cn='aMQTT',
                     output_dir=str(temp_directory),
                     ca_key_fn=str(ca_key), ca_crt_fn=str(ca_crt))
    server_key = temp_directory / "server.key"
    server_crt = temp_directory / "server.crt"
    yield server_key, server_crt

@pytest.fixture
def device_creds(ca_creds, temp_directory):
    ca_key, ca_crt = ca_creds
    get_device_creds(country='US', org_name='aMQTT',
                     device_id="mydeviceid", uri='test.amqtt.io',
                     output_dir=str(temp_directory),
                     ca_key_fn=str(ca_key), ca_crt_fn=str(ca_crt))
    yield temp_directory / "mydeviceid.key", temp_directory / "mydeviceid.crt"

def test_device_cert(temp_directory, ca_creds, server_creds, device_creds):
    ca_key, ca_crt = ca_creds
    server_key, server_crt = server_creds
    device_key, device_crt = device_creds

    assert ca_key.exists()
    assert ca_crt.exists()
    assert server_key.exists()
    assert server_crt.exists()
    assert device_key.exists()
    assert device_crt.exists()

    r = subprocess.run(f"openssl x509 -in {str(device_crt)} -noout -text", shell=True, capture_output=True, text=True, check=True)

    assert "URI:spiffe://test.amqtt.io/device/mydeviceid, DNS:mydeviceid.local" in r.stdout

@pytest.fixture
def ssl_object_mock(device_creds):
    device_key, device_crt = device_creds

    with device_crt.open("rb") as f:
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
    mock = MagicMock()
    mock.getpeercert.return_value = crypto.dump_certificate(crypto.FILETYPE_ASN1, cert)
    yield mock


@pytest.mark.parametrize("uri_domain,client_id,expected_result", [
    ('test.amqtt.io', 'mydeviceid', True),
    ('test.amqtt.io', 'notmydeviceid', False),
    ('other.amqtt.io', 'mydeviceid', False),
])
@pytest.mark.asyncio
async def test_cert_plugin(ssl_object_mock, uri_domain, client_id, expected_result):

    empty_cfg = {
        'listeners': {'default': {'type':'tcp', 'bind':'127.0.0.1:1883'}},
        'plugins': {}
    }

    bc = BrokerContext(broker=Broker(config=empty_cfg))
    bc.config = CertificateAuthPlugin.Config(uri_domain=uri_domain)

    cert_auth_plugin = CertificateAuthPlugin(bc)

    s = Session()
    s.client_id = client_id
    s.ssl_object = ssl_object_mock

    assert await cert_auth_plugin.authenticate(session=s) == expected_result


@pytest.mark.asyncio
async def test_client_broker_cert_authentication(ca_creds, server_creds, device_creds):
    ca_key, ca_crt = ca_creds
    server_key, server_crt = server_creds
    device_key, device_crt = device_creds
    broker_config = {
        'listeners': {
            'default': {
                'type':'tcp',
                'bind':'127.0.0.1:8883',
                'ssl': True,
                'keyfile': server_key,
                'certfile': server_crt,
                'cafile': ca_crt,
            }
        },
        'plugins': {
            'amqtt.plugins.logging_amqtt.PacketLoggerPlugin':{},
            'amqtt.contrib.cert.CertificateAuthPlugin': {'uri_domain': 'test.amqtt.io'},
        }
    }

    b = Broker(config=broker_config)
    await b.start()
    await asyncio.sleep(1)

    client_config = {
        'auto_reconnect': False,
        'cafile': ca_crt,
        'certfile': device_crt,
        'keyfile': device_key,
    }

    c = MQTTClient(config=client_config, client_id='mydeviceid')
    await c.connect('mqtts://127.0.0.1:8883')
    await asyncio.sleep(1)
    await c.disconnect()

    await b.shutdown()