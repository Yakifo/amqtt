import asyncio
import inspect
import logging
from functools import partial
from importlib.metadata import EntryPoint
from logging import getLogger
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Coroutine
from unittest.mock import patch

import pytest

import amqtt.plugins
from amqtt.broker import Broker, BrokerContext
from amqtt.client import MQTTClient
from amqtt.errors import PluginInitError, PluginImportError
from amqtt.events import MQTTEvents, BrokerEvents
from amqtt.mqtt.constants import QOS_0, QOS_2, QOS_1
from amqtt.plugins.base import BasePlugin
from amqtt.contexts import BaseContext
from amqtt.plugins.persistence import RetainedMessage

_INVALID_METHOD: str = "invalid_foo"
_PLUGIN: str = "Plugin"

logger = logging.getLogger(__name__)

class _TestContext(BaseContext):
    def __init__(self) -> None:
        super().__init__()
        self.config: dict[str, Any] = {"auth": {}}
        self.logger = getLogger(__name__)


def _verify_module(module: ModuleType, plugin_module_name: str) -> None:
    if not module.__name__.startswith(plugin_module_name):
        return

    for name, clazz in inspect.getmembers(module, inspect.isclass):
        if not name.endswith(_PLUGIN) or name == _PLUGIN:
            continue

        obj = clazz(_TestContext())
        with pytest.raises(
            AttributeError,
            match=f"'{name}' object has no attribute '{_INVALID_METHOD}'",
        ):
            getattr(obj, _INVALID_METHOD)
        assert hasattr(obj, _INVALID_METHOD) is False

    for _, obj in inspect.getmembers(module, inspect.ismodule):
        _verify_module(obj, plugin_module_name)


def removesuffix(self: str, suffix: str) -> str:
    """Compatibility for Python versions prior to 3.9."""
    if suffix and self.endswith(suffix):
        return self[: -len(suffix)]
    return self[:]


def test_plugins_correct_has_attr() -> None:
    """Test plugins to ensure they correctly handle the 'has_attr' check."""
    module = amqtt.plugins
    for file in Path(module.__file__).parent.rglob("*.py"):
        if not Path(file).is_file():
            continue

        name = file.as_posix().replace("/", ".")
        name = name[name.find(module.__name__) : -3]
        name = removesuffix(name, ".__init__")

        __import__(name)

    _verify_module(module, module.__name__)


class MockInitErrorPlugin(BasePlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        raise KeyError


@pytest.mark.asyncio
async def test_plugin_exception_while_init() -> None:

    config = {
        "listeners": {
            "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        },
        'sys_interval': 1,
        'plugins':{
            'tests.plugins.test_plugins.MockInitErrorPlugin':{}
        }
    }

    with pytest.raises(PluginInitError):
        _ = Broker(plugin_namespace='tests.mock_plugins', config=config)


@pytest.mark.asyncio
async def test_plugin_exception_while_loading() -> None:

    config = {
        "listeners": {
            "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        },
        'sys_interval': 1,
        'plugins':{
            'tests.plugins.mock_plugins.MockImportErrorPlugin':{}
        }
    }

    with pytest.raises(PluginImportError):
        _ = Broker(plugin_namespace='tests.mock_plugins', config=config)


class AllEventsPlugin(BasePlugin[BaseContext]):
    """A plugin to verify all events get sent to plugins."""
    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        self.test_flags = { events:False for events in list(MQTTEvents) + list(BrokerEvents)}

    async def call_method(self, event_name: str, **kwargs: Any) -> None:
        assert event_name in self.test_flags
        self.test_flags[event_name] = True

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, None]]:
        """Dynamically handle calls to methods starting with 'on_'."""

        if name.startswith("on_"):
            event_name = name.replace('on_', '')
            return partial(self.call_method, event_name)

        if name not in ('authenticate', 'topic_filtering'):
            pytest.fail(f'unexpected method called: {name}')


@pytest.mark.asyncio
async def test_all_plugin_events():

    config = {
        "listeners": {
            "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        },
        'sys_interval': 1,
        'plugins':{
            'amqtt.plugins.authentication.AnonymousAuthPlugin': {},
            'tests.plugins.test_plugins.AllEventsPlugin': {}
        }
    }

    broker = Broker(plugin_namespace='tests.mock_plugins', config=config)

    await broker.start()
    await asyncio.sleep(2)

    # make sure all expected events get triggered
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1:1883/")
    await client.subscribe([('my/test/topic', QOS_0),])
    await client.publish('test/topic', b'my test message', retain=True)
    await client.unsubscribe(['my/test/topic',])
    await client.disconnect()
    await asyncio.sleep(1)

    # get the plugin so it doesn't get gc on shutdown
    test_plugin = broker.plugins_manager.get_plugin('AllEventsPlugin')
    await broker.shutdown()
    await asyncio.sleep(1)

    assert all(test_plugin.test_flags.values()), f'event not received: {[event for event, value in test_plugin.test_flags.items() if not value]}'


class RetainedMessageEventPlugin(BasePlugin[BrokerContext]):
    """A plugin to verify all events get sent to plugins."""
    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)
        self.topic_retained_message_flag = False
        self.session_retained_message_flag = False
        self.topic_clear_retained_message_flag = False

    async def on_broker_retained_message(self, *, client_id: str | None, retained_message: RetainedMessage) -> None:
        """retaining message event handler."""
        if client_id:
            session = self.context.get_session(client_id)
            assert session.transitions.state != "connected"
            logger.debug("retained message event fired for offline client")
            self.session_retained_message_flag = True
        else:
            if not retained_message.data:
                logger.debug("retained message event fired for clearing a topic")
                self.topic_clear_retained_message_flag = True
            else:
                logger.debug("retained message event fired for setting a topic")
                self.topic_retained_message_flag = True


@pytest.mark.asyncio
async def test_retained_message_plugin_event():

    config = {
        "listeners": {
            "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        },
        'sys_interval': 1,
        'plugins':[{'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': False}},
                   {'tests.plugins.test_plugins.RetainedMessageEventPlugin': {}}]
        }

    broker = Broker(plugin_namespace='tests.mock_plugins', config=config)

    await broker.start()
    await asyncio.sleep(0.1)

    # make sure all expected events get triggered
    client1 = MQTTClient(config={'auto_reconnect': False})
    await client1.connect("mqtt://myUsername@127.0.0.1:1883/", cleansession=False)
    await client1.subscribe([('test/topic', QOS_1),])
    await client1.publish('test/retained', b'message should be retained for test/retained', retain=True)
    await asyncio.sleep(0.1)
    await client1.disconnect()

    client2 = MQTTClient(config={'auto_reconnect': False})
    await client2.connect("mqtt://myOtherUsername@127.0.0.1:1883/", cleansession=True)
    await client2.publish('test/topic', b'message should be retained for myUsername since subscription was qos > 0')
    await client2.publish('test/retained', b'', retain=True)  # should clear previously retained message
    await asyncio.sleep(0.1)
    await client2.disconnect()
    await asyncio.sleep(0.1)

    # get the plugin so it doesn't get gc on shutdown
    test_plugin = broker.plugins_manager.get_plugin('RetainedMessageEventPlugin')
    await broker.shutdown()
    await asyncio.sleep(0.1)

    assert test_plugin.topic_retained_message_flag, "message to topic wasn't retained"
    assert test_plugin.session_retained_message_flag, "message to disconnected client wasn't retained"
    assert test_plugin.topic_clear_retained_message_flag, "message to retained topic wasn't cleared"
