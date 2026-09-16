import ast
import asyncio
import logging
import multiprocessing
import signal
import subprocess
import sys

from pathlib import Path

from typer.testing import CliRunner

from amqtt.mqtt.constants import QOS_0
from samples.http_server_integration import main as http_server_main
from samples.unix_sockets import app as unix_sockets_app

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from samples.broker_acl import config as broker_acl_config
from samples.broker_taboo import config as broker_taboo_config
from samples.broker_dollar_topics import config as broker_dollar_topics_config

logger = logging.getLogger(__name__)

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
IGNORED_SAMPLE_FILES = frozenset()


def _is_sample_marker(decorator: ast.expr) -> bool:
    return (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "sample"
        and isinstance(decorator.func.value, ast.Attribute)
        and decorator.func.value.attr == "mark"
        and isinstance(decorator.func.value.value, ast.Name)
        and decorator.func.value.value.id == "pytest"
    )


def _sample_marker_files() -> set[str]:
    tree = ast.parse(Path(__file__).read_text())
    sample_files = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if _is_sample_marker(decorator):
                    sample_files.update(
                        arg.value
                        for arg in decorator.args
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    )

    return sample_files


def test_all_sample_files_are_accounted_for():
    sample_files = {path.name for path in SAMPLES_DIR.glob("*.py")}
    marked_sample_files = _sample_marker_files()
    missing_tests = sorted(sample_files - marked_sample_files - IGNORED_SAMPLE_FILES)
    stale_markers = sorted(marked_sample_files - sample_files)
    stale_ignored = sorted(IGNORED_SAMPLE_FILES - sample_files)

    assert not missing_tests, f"Add @pytest.mark.sample(...) coverage for new sample files: {missing_tests}"
    assert not stale_markers, f"Remove stale sample markers: {stale_markers}"
    assert not stale_ignored, f"Remove stale ignored sample entries: {stale_ignored}"


@pytest.mark.asyncio
@pytest.mark.sample("broker_acl.py")
async def test_broker_acl():
    broker_acl_script = Path(__file__).parent.parent / "samples/broker_acl.py"
    process = subprocess.Popen([sys.executable, broker_acl_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Send the interrupt signal
    await asyncio.sleep(2)
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "Broker closed" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")


@pytest.mark.asyncio
@pytest.mark.sample("broker_custom_plugin.py")
async def test_broker_custom_plugin():
    broker_custom_plugin_script = SAMPLES_DIR / "broker_custom_plugin.py"
    process = subprocess.Popen([sys.executable, broker_custom_plugin_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "Broker closed" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")


@pytest.mark.asyncio
@pytest.mark.sample("broker_simple.py")
async def test_broker_simple():
    broker_simple_script = Path(__file__).parent.parent / "samples/broker_simple.py"
    process = subprocess.Popen([sys.executable, broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    # Send the interrupt signal
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    has_broker_closed = "Broker closed" in stderr.decode("utf-8")
    has_loop_stopped = "Broadcast loop stopped by exception" in stderr.decode("utf-8")

    assert has_broker_closed or has_loop_stopped, "Broker didn't close correctly."


@pytest.mark.asyncio
@pytest.mark.sample("broker_start.py")
async def test_broker_start():
    broker_start_script = Path(__file__).parent.parent / "samples/broker_start.py"
    process = subprocess.Popen([sys.executable, broker_start_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    # Send the interrupt signal to stop broker
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "Broker closed" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")


@pytest.mark.asyncio
@pytest.mark.sample("broker_taboo.py")
async def test_broker_taboo():
    broker_taboo_script = Path(__file__).parent.parent / "samples/broker_taboo.py"
    process = subprocess.Popen([sys.executable, broker_taboo_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    # Send the interrupt signal to stop broker
    process.send_signal(signal.SIGINT)
    stdout, stderr = process.communicate()
    logger.debug(stderr.decode("utf-8"))
    assert "INFO :: amqtt.broker :: Broker closed" in stderr.decode("utf-8")
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")


@pytest.mark.asyncio
@pytest.mark.sample("client_keepalive.py")
async def test_client_keepalive():

    broker = Broker()
    await broker.start()
    await asyncio.sleep(2)

    keep_alive_script = Path(__file__).parent.parent / "samples/client_keepalive.py"
    process = subprocess.Popen([sys.executable, keep_alive_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(1)

    stdout, stderr = await asyncio.to_thread(process.communicate)
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.mark.asyncio
@pytest.mark.sample("client_publish.py")
async def test_client_publish():
    broker = Broker()
    await broker.start()
    await asyncio.sleep(2)

    client_publish = Path(__file__).parent.parent / "samples/client_publish.py"
    process = subprocess.Popen([sys.executable, client_publish], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
@pytest.mark.sample("client_publish_ssl.py")
async def test_client_publish_ssl(broker_ssl_config, rsa_keys):
    certfile, _ = rsa_keys
    # generate a self-signed certificate for this test

    # start a secure broker
    broker = Broker(config=broker_ssl_config)
    await broker.start()
    await asyncio.sleep(2)
    # run the sample
    client_publish_ssl_script = Path(__file__).parent.parent / "samples/client_publish_ssl.py"
    process = subprocess.Popen([sys.executable, client_publish_ssl_script, '--cert', certfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)
    stdout, stderr = process.communicate()

    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()


@pytest.mark.asyncio
@pytest.mark.sample("client_publish_acl.py")
async def test_client_publish_acl():

    broker = Broker()
    await broker.start()
    await asyncio.sleep(2)

    broker_simple_script = Path(__file__).parent.parent / "samples/client_publish_acl.py"
    process = subprocess.Popen([sys.executable, broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
@pytest.mark.sample("client_publish_ws.py")
async def test_client_publish_ws():
    # start a secure broker
    broker = Broker(config=broker_ws_config)
    await broker.start()
    await asyncio.sleep(2)
    # run the sample

    client_publish_ssl_script = Path(__file__).parent.parent / "samples/client_publish_ws.py"
    process = subprocess.Popen([sys.executable, client_publish_ssl_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
@pytest.mark.sample("client_subscribe.py")
async def test_client_subscribe():

    # start a standard broker
    broker = Broker(config=broker_std_config)
    await broker.start()
    await asyncio.sleep(1)

    # run the sample
    client_subscribe_script = Path(__file__).parent.parent / "samples/client_subscribe.py"

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(client_subscribe_script),
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
@pytest.mark.sample("client_subscribe_acl.py")
async def test_client_subscribe_plugin_acl():
    broker = Broker(config=broker_acl_config)
    await broker.start()

    broker_simple_script = Path(__file__).parent.parent / "samples/client_subscribe_acl.py"
    process = subprocess.Popen([sys.executable, broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
@pytest.mark.sample("client_subscribe_acl.py")
async def test_client_subscribe_plugin_taboo():
    broker = Broker(config=broker_taboo_config)
    await broker.start()

    broker_simple_script = Path(__file__).parent.parent / "samples/client_subscribe_acl.py"
    process = subprocess.Popen([sys.executable, broker_simple_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    # Force "spawn" so the child starts a fresh interpreter with no event loop.
    # On Linux the default start method is "fork", which would inherit the running
    # pytest-asyncio event loop and break `web.run_app` inside the sample's main().
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=http_server_main)
    p.start()
    yield p
    p.terminate()
    p.join()


async def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    """Poll until the server is accepting connections (spawn startup can be slow)."""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            _, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError:
            if asyncio.get_event_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.1)


@pytest.mark.asyncio
@pytest.mark.sample("http_server_integration.py")
async def test_external_http_server(external_http_server):

    await _wait_for_port("127.0.0.1", 8080)
    client = MQTTClient(config={'auto_reconnect': False})
    await client.connect("ws://127.0.0.1:8080/mqtt")
    assert client.session is not None
    await client.publish("my/topic", b'test message')
    await client.disconnect()
    # Send the interrupt signal
    await asyncio.sleep(1)


@pytest.mark.asyncio
@pytest.mark.sample("unix_sockets.py")
async def test_unix_connection():

    unix_socket_script = Path(__file__).parent.parent / "samples/unix_sockets.py"
    broker_process = subprocess.Popen([sys.executable, "-m", "coverage", "run", unix_socket_script, "broker", "-s", "/tmp/mqtt"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # start the broker
    await asyncio.sleep(1)

    # start the client
    client_process = subprocess.Popen([sys.executable, "-m", "coverage", "run", unix_socket_script, "client", "-s", "/tmp/mqtt"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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


@pytest.mark.sample("reloadable_external_tls_listener.py")
def test_reloadable_external_tls_listener_sample_configuration(rsa_keys):
    import ssl

    from amqtt.contexts import ListenerType
    from samples.reloadable_external_tls_listener import build_broker_config, build_tls_context_factory

    certfile, keyfile = rsa_keys

    broker_config = build_broker_config()
    assert broker_config.listeners["default"].type == ListenerType.EXTERNAL

    context = build_tls_context_factory(certfile=certfile, keyfile=keyfile)()
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_NONE


@pytest.mark.asyncio
@pytest.mark.sample("broker_dollar_topics.py")
async def test_allowable_dollar_topics():

    broker = Broker(config=broker_dollar_topics_config)
    await broker.start()
    await asyncio.sleep(1)

    rcv_client = MQTTClient(config={'auto_reconnect': False})
    await rcv_client.connect("ws://127.0.0.1:8080/mqtt")
    await rcv_client.subscribe([("$my/dollar/topic", QOS_0),])
    assert rcv_client.session is not None

    pub_client = MQTTClient(config={'auto_reconnect': False})
    await pub_client.connect("ws://127.0.0.1:8080/mqtt")
    await pub_client.publish("$my/dollar/topic", b'test message')
    await asyncio.sleep(1)
    await pub_client.disconnect()

    message = await rcv_client.deliver_message()
    assert message is not None
    assert message.publish_packet is not None
    assert message.data == b'test message'
    await rcv_client.disconnect()

    await asyncio.sleep(0.1)
    await broker.shutdown()
    await asyncio.sleep(0.1)
