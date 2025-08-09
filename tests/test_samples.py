import asyncio
import logging
import signal
import subprocess

from multiprocessing import Process
from pathlib import Path

from typer.testing import CliRunner

from samples.http_server_integration import main as http_server_main
from samples.unix_sockets import app as unix_sockets_app

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from samples.broker_acl import config as broker_acl_config
from samples.broker_taboo import config as broker_taboo_config

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_broker_acl():
    broker_acl_script = Path(__file__).parent.parent / "samples/broker_acl.py"
    process = subprocess.Popen(["python", broker_acl_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Send the interrupt signal
    await asyncio.sleep(2)
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "Broker closed" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")


@pytest.mark.asyncio
async def test_broker_simple():
    broker_simple_script = Path(__file__).parent.parent / "samples/broker_simple.py"
    process = subprocess.Popen(["python", broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    # Send the interrupt signal
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    has_broker_closed = "Broker closed" in stderr.decode("utf-8")
    has_loop_stopped = "Broadcast loop stopped by exception" in stderr.decode("utf-8")

    assert has_broker_closed or has_loop_stopped, "Broker didn't close correctly."


@pytest.mark.asyncio
async def test_broker_start():
    broker_start_script = Path(__file__).parent.parent / "samples/broker_start.py"
    process = subprocess.Popen(["python", broker_start_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    # Send the interrupt signal to stop broker
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "Broker closed" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")


@pytest.mark.asyncio
async def test_broker_taboo():
    broker_taboo_script = Path(__file__).parent.parent / "samples/broker_taboo.py"
    process = subprocess.Popen(["python", broker_taboo_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    # Send the interrupt signal to stop broker
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "INFO :: amqtt.broker :: Broker closed" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")


@pytest.mark.timeout(25)
@pytest.mark.asyncio
async def test_client_keepalive():

    broker = Broker()
    await broker.start()
    await asyncio.sleep(2)

    keep_alive_script = Path(__file__).parent.parent / "samples/client_keepalive.py"
    process = subprocess.Popen(["python", keep_alive_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(1)

    stdout, stderr = process.communicate()
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.mark.asyncio
async def test_client_publish():
    broker = Broker()
    await broker.start()
    await asyncio.sleep(2)

    client_publish = Path(__file__).parent.parent / "samples/client_publish.py"
    process = subprocess.Popen(["python", client_publish], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    stdout, stderr = process.communicate()
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.fixture
def broker_ssl_config(rsa_keys):
    certfile, keyfile = rsa_keys
    return {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": "0.0.0.0:8883",
                "ssl": True,
                "certfile": certfile,
                "keyfile": keyfile,
            }
        },
        "auth": {
            "allow-anonymous": True,
            "plugins": ["auth_anonymous"]
        }
    }

@pytest.mark.asyncio
async def test_client_publish_ssl(broker_ssl_config, rsa_keys):
    certfile, _ = rsa_keys
    # generate a self-signed certificate for this test

    # start a secure broker
    broker = Broker(config=broker_ssl_config)
    await broker.start()
    await asyncio.sleep(2)
    # run the sample
    client_publish_ssl_script = Path(__file__).parent.parent / "samples/client_publish_ssl.py"
    process = subprocess.Popen(["python", client_publish_ssl_script, '--cert', certfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)
    stdout, stderr = process.communicate()

    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.mark.asyncio
async def test_client_publish_acl():

    broker = Broker()
    await broker.start()
    await asyncio.sleep(2)

    broker_simple_script = Path(__file__).parent.parent / "samples/client_publish_acl.py"
    process = subprocess.Popen(["python", broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Send the interrupt signal
    await asyncio.sleep(2)

    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()

broker_ws_config = {
    "listeners": {
        "default": {
            "type": "ws",
            "bind": "0.0.0.0:8080",
        }
    },
    "auth": {
        "allow-anonymous": True,
        "plugins": ["auth_anonymous"]
    }
}

@pytest.mark.asyncio
async def test_client_publish_ws():
    # start a secure broker
    broker = Broker(config=broker_ws_config)
    await broker.start()
    await asyncio.sleep(2)
    # run the sample

    client_publish_ssl_script = Path(__file__).parent.parent / "samples/client_publish_ws.py"
    process = subprocess.Popen(["python", client_publish_ssl_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)
    stdout, stderr = process.communicate()

    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


broker_std_config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        }
    },
    'sys_interval':2,
    "auth": {
        "allow-anonymous": True,
        "plugins": ["auth_anonymous"]
    }
}


@pytest.mark.asyncio
async def test_client_subscribe():

    # start a standard broker
    broker = Broker(config=broker_std_config)
    await broker.start()
    await asyncio.sleep(1)

    # run the sample
    client_subscribe_script = Path(__file__).parent.parent / "samples/client_subscribe.py"

    process = await asyncio.create_subprocess_shell(
        " ".join(["python", str(client_subscribe_script)]),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    assert "ERROR" not in stdout.decode("utf-8")
    assert "Exception" not in stdout.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.mark.asyncio
async def test_client_subscribe_plugin_acl():
    broker = Broker(config=broker_acl_config)
    await broker.start()

    broker_simple_script = Path(__file__).parent.parent / "samples/client_subscribe_acl.py"
    process = subprocess.Popen(["python", broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Send the interrupt signal
    await asyncio.sleep(2)
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "Subscribed results: [128, 1, 128, 1, 128, 1]" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.mark.asyncio
async def test_client_subscribe_plugin_taboo():
    broker = Broker(config=broker_taboo_config)
    await broker.start()

    broker_simple_script = Path(__file__).parent.parent / "samples/client_subscribe_acl.py"
    process = subprocess.Popen(["python", broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Send the interrupt signal
    await asyncio.sleep(2)
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "Subscribed results: [1, 1, 128, 1, 1, 1]" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.fixture
def external_http_server():
    p = Process(target=http_server_main)
    p.start()
    yield p
    p.terminate()


@pytest.mark.asyncio
async def test_external_http_server(external_http_server):

    await asyncio.sleep(1)
    client = MQTTClient(config={'auto_reconnect': False})
    await client.connect("ws://127.0.0.1:8080/mqtt")
    assert client.session is not None
    await client.publish("my/topic", b'test message')
    await client.disconnect()
    # Send the interrupt signal
    await asyncio.sleep(1)


@pytest.mark.asyncio
async def test_unix_connection():

    unix_socket_script = Path(__file__).parent.parent / "samples/unix_sockets.py"
    broker_process = subprocess.Popen(["python", unix_socket_script, "broker", "-s", "/tmp/mqtt"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # start the broker
    await asyncio.sleep(1)

    # start the client
    client_process = subprocess.Popen(["python", unix_socket_script, "client", "-s", "/tmp/mqtt"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    await asyncio.sleep(3)

    # stop the client (ctrl-c)
    client_process.send_signal(signal.SIGINT)
    _ = client_process.communicate()

    # stop the broker (ctrl-c)
    broker_process.send_signal(signal.SIGINT)
    broker_stdout, broker_stderr = broker_process.communicate()

    logger.debug(broker_stderr.decode("utf-8"))

    # verify that the broker received client connected/disconnected
    assert "on_broker_client_connected" in broker_stderr.decode("utf-8")
    assert "on_broker_client_disconnected" in broker_stderr.decode("utf-8")
