import unittest.mock
import os.path

import pytest

import amqtt.broker

pytest_plugins = ["pytest_logdog"]

test_config = {
    "listeners": {
        "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
    },
    "sys_interval": 0,
    "auth": {
        "allow-anonymous": True,
    },
}


test_config_acl = {
    "listeners": {
        "default": {"type": "tcp", "bind": "127.0.0.1:1884", "max_connections": 10},
    },
    "sys_interval": 0,
    "auth": {
        "plugins": ["auth_file"],
        "password-file": os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "plugins", "passwd"
        ),
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


@pytest.fixture(scope="function")
def mock_plugin_manager():
    with unittest.mock.patch("amqtt.broker.PluginManager") as plugin_manager:
        yield plugin_manager


@pytest.fixture(scope="function")
async def broker(mock_plugin_manager):
    # just making sure the mock is in place before we start our broker
    assert mock_plugin_manager is not None

    broker = amqtt.broker.Broker(test_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    assert broker.transitions.is_started()
    assert broker._sessions == {}
    assert "default" in broker._servers

    yield broker

    if not broker.transitions.is_stopped():
        await broker.shutdown()


@pytest.fixture(scope="function")
async def acl_broker():
    broker = amqtt.broker.Broker(
        test_config_acl, plugin_namespace="amqtt.broker.plugins"
    )
    await broker.start()
    assert broker.transitions.is_started()
    assert broker._sessions == {}
    assert "default" in broker._servers

    yield broker

    if not broker.transitions.is_stopped():
        await broker.shutdown()
