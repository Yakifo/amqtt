import unittest.mock

import pytest

import hbmqtt.broker

test_config = {
    "listeners": {
        "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
    },
    "sys_interval": 0,
    "auth": {
        "allow-anonymous": True,
    },
}


@pytest.fixture(scope="function")
def mock_plugin_manager():
    with unittest.mock.patch("hbmqtt.broker.PluginManager") as plugin_manager:
        yield plugin_manager


@pytest.fixture(scope="function")
async def broker(mock_plugin_manager):
    # just making sure the mock is in place before we start our broker
    assert mock_plugin_manager is not None

    broker = hbmqtt.broker.Broker(test_config, plugin_namespace="hbmqtt.test.plugins")
    await broker.start()
    assert broker.transitions.is_started()
    assert broker._sessions == {}
    assert "default" in broker._servers

    yield broker

    if not broker.transitions.is_stopped():
        await broker.shutdown()
