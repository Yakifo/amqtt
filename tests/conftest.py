import logging
from pathlib import Path
import tempfile
from typing import Any
import unittest.mock
import urllib.request

import pytest

from amqtt.broker import Broker

log = logging.getLogger(__name__)

pytest_plugins = ["pytest_logdog"]

test_config = {
    "listeners": {
        "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        "ws": {"type": "ws", "bind": "127.0.0.1:8080", "max_connections": 10},
        "wss": {"type": "ws", "bind": "127.0.0.1:8081", "max_connections": 10},
    },
    "sys_interval": 0,
    "auth": {
        "allow-anonymous": True,
    },
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
    with unittest.mock.patch("amqtt.broker.PluginManager") as plugin_manager:
        yield plugin_manager


@pytest.fixture
async def broker_fixture():
    broker = Broker(test_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    assert broker.transitions.is_started()
    assert broker._sessions == {}
    assert "default" in broker._servers

    yield broker

    if not broker.transitions.is_stopped():
        await broker.shutdown()


@pytest.fixture
async def broker(mock_plugin_manager):
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
