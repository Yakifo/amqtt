import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import ssl
from unittest.mock import MagicMock

from OpenSSL import crypto

import pytest

from amqtt.broker import BrokerContext, Broker
from amqtt.contrib.cert import CertificateAuthPlugin
from amqtt.scripts.server_creds import server_creds as get_server_creds
from amqtt.scripts.device_creds import device_creds as get_device_creds
from amqtt.session import Session

logger = logging.getLogger(__name__)

@pytest.fixture
def temp_directory():
    temp_dir = Path(tempfile.mkdtemp(prefix="amqtt-test-"))
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def server_creds(temp_directory):
    server_key = temp_directory / "ca.key"
    server_crt = temp_directory / "ca.crt"
    get_server_creds(country='US', state='NY',
                     locality='NY', org_name='aMQTT', cn='aMQTT',
                     server_key=str(server_key), server_crt=str(server_crt))
    yield server_key, server_crt

@pytest.fixture
def device_creds(temp_directory, server_creds):
    server_key, server_crt = server_creds
    get_device_creds(country='US', org_name='aMQTT',
                     device_id="mydeviceid", uri='test.amqtt.io',
                     output_dir=str(temp_directory),
                     server_key=str(server_key), server_crt=str(server_crt))
    yield temp_directory / "mydeviceid.key", temp_directory / "mydeviceid.crt"

def test_device_cert(temp_directory, server_creds, device_creds):
    server_key, server_crt = server_creds
    device_key, device_crt = device_creds

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

# @pytest.mark.asyncio
# async def test_missing_x509_extension():
#     pass

@pytest.mark.asyncio
async def test_client_broker_cert_authentication():
    raise NotImplementedError()
