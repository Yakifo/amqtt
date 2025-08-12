import logging
import subprocess
from pathlib import Path
import tempfile
from typing import Any
import unittest.mock
import urllib.request

import pytest

from amqtt.broker import Broker
from amqtt.contexts import BaseContext
from amqtt.plugins.base import BasePlugin

log = logging.getLogger(__name__)

pytest_plugins = ["pytest_logdog"]

@pytest.fixture
def rsa_keys():
    tmp_dir = tempfile.TemporaryDirectory(prefix='amqtt-test-')
    cert = Path(tmp_dir.name) / "cert.pem"
    key = Path(tmp_dir.name) / "key.pem"
    cmd = f'openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout {key} -out {cert} -subj "/CN=localhost"'
    subprocess.run(cmd, shell=True, capture_output=True, text=True)
    yield cert, key
    tmp_dir.cleanup()


@pytest.fixture
def test_config(rsa_keys):
    certfile, keyfile = rsa_keys
    with pytest.warns(DeprecationWarning):
        yield {
            "listeners": {
                "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 15},
                "mqtts": {
                    "type": "tcp",
                    "bind": "127.0.0.1:1884",
                    "max_connections": 15,
                    "ssl": True,
                    "certfile": certfile,
                    "keyfile": keyfile
                },
                "ws": {"type": "ws", "bind": "127.0.0.1:8080", "max_connections": 15},
                "wss": {
                    "type": "ws",
                    "bind": "127.0.0.1:8081",
                    "max_connections": 15,
                    "ssl": True,
                    'certfile': certfile,
                    'keyfile': keyfile},
            },
            "sys_interval": 0,
            "auth": {
                "allow-anonymous": True,
            }
        }

test_config_acl: dict[str, int | dict[str, Any]] = {
    "listeners": {
        "default": {"type": "tcp", "bind": "127.0.0.1:1884", "max_connections": 10},
    },
    "sys_interval": 0,
    "auth": {
        "plugins": ["auth_file"],
        "password-file": Path(__file__).resolve().parent / "plugins" / "passwd",
    },
    "topic-check": {
        "enabled": True,
        "plugins": ["topic_acl"],
        "acl": {
            "user1": ["public/#"],
            "user2": ["#"],
        },
        "publish-acl": {"user1": ["public/subtopic/#"]},
    },
}


@pytest.fixture
def mock_plugin_manager():
    with (unittest.mock.patch("amqtt.broker.PluginManager") as plugin_manager):
        plugin_manager_instance = plugin_manager.return_value

        # disable topic filtering when using the mock manager
        plugin_manager_instance.is_topic_filtering_enabled.return_value = False

        # allow any connection when using the mock manager
        plugin_manager_instance.map_plugin_auth = unittest.mock.AsyncMock(return_value={ BasePlugin(BaseContext()): True })

        yield plugin_manager


@pytest.fixture
async def broker_fixture(test_config):
    broker = Broker(test_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    assert broker.transitions.is_started()
    assert broker._sessions == {}
    assert "default" in broker._servers

    yield broker

    if not broker.transitions.is_stopped():
        await broker.shutdown()


@pytest.fixture
async def broker(mock_plugin_manager, test_config):
    # just making sure the mock is in place before we start our broker
    assert mock_plugin_manager is not None

    broker = Broker(test_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    assert broker.transitions.is_started()
    assert broker._sessions == {}
    assert "default" in broker._servers

    yield broker

    if not broker.transitions.is_stopped():
        await broker.shutdown()


@pytest.fixture
async def acl_broker():
    broker = Broker(
        test_config_acl,
        plugin_namespace="amqtt.broker.plugins",
    )
    await broker.start()
    assert broker.transitions.is_started()
    assert broker._sessions == {}
    assert "default" in broker._servers

    yield broker

    if not broker.transitions.is_stopped():
        await broker.shutdown()


@pytest.fixture(scope="module")
def ca_file_fixture():
    temp_dir = Path(tempfile.mkdtemp(prefix="amqtt-test-"))
    url = "http://test.mosquitto.org/ssl/mosquitto.org.crt"
    ca_file = temp_dir / "mosquitto.org.crt"
    urllib.request.urlretrieve(url, str(ca_file))
    log.info(f"Stored mosquitto cert at {ca_file}")

    # Yield the CA file path for tests
    yield ca_file

    # Cleanup after the tests
    if temp_dir.exists():
        for file in temp_dir.iterdir():
            file.unlink()
        temp_dir.rmdir()


def pytest_addoption(parser):
    parser.addoption(
        "--mock-docker",
        action="store",
        default="false",
        help="for environments where docker isn't available, mock calls which require docker",
    )