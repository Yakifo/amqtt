import asyncio
import inspect
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
from amqtt.errors import PluginError, PluginInitError, PluginImportError
from amqtt.events import MQTTEvents, BrokerEvents
from amqtt.mqtt.constants import QOS_0
from amqtt.plugins.base import BasePlugin
from amqtt.plugins.contexts import BaseContext

_INVALID_METHOD: str = "invalid_foo"
_PLUGIN: str = "Plugin"


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
    class MockEntryPoints:

        def select(self, group) -> list[EntryPoint]:
            match group:
                case 'tests.mock_plugins':
                    return [
                            EntryPoint(name='TestExceptionPlugin', group='tests.mock_plugins', value='tests.plugins.test_plugins:MockInitErrorPlugin'),
                        ]
                case _:
                    return list()

    with patch("amqtt.plugins.manager.entry_points", side_effect=MockEntryPoints) as mocked_mqtt_publish:

        config = {
            "listeners": {
                "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
            },
            'sys_interval': 1
        }

        with pytest.raises(PluginInitError):
            _ = Broker(plugin_namespace='tests.mock_plugins', config=config)


@pytest.mark.asyncio
async def test_plugin_exception_while_loading() -> None:
    class MockEntryPoints:

        def select(self, group) -> list[EntryPoint]:
            match group:
                case 'tests.mock_plugins':
                    return [
                            EntryPoint(name='TestExceptionPlugin', group='tests.mock_plugins', value='tests.plugins.mock_plugins:MockImportErrorPlugin'),
                        ]
                case _:
                    return list()

    with patch("amqtt.plugins.manager.entry_points", side_effect=MockEntryPoints) as mocked_mqtt_publish:

        config = {
            "listeners": {
                "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
            },
            'sys_interval': 1
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
    class MockEntryPoints:

        def select(self, group) -> list[EntryPoint]:
            match group:
                case 'tests.mock_plugins':
                    return [
                            EntryPoint(name='AllEventsPlugin', group='tests.mock_plugins', value='tests.plugins.test_plugins:AllEventsPlugin'),
                        ]
                case _:
                    return list()

    # patch the entry points so we can load our test plugin
    with patch("amqtt.plugins.manager.entry_points", side_effect=MockEntryPoints) as mocked_mqtt_publish:

        config = {
            "listeners": {
                "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
            },
            'sys_interval': 1
        }


        broker = Broker(plugin_namespace='tests.mock_plugins', config=config)

        await broker.start()
        await asyncio.sleep(2)

        # make sure all expected events get triggered
        client = MQTTClient()
        await client.connect("mqtt://127.0.0.1:1883/")
        await client.subscribe([('my/test/topic', QOS_0),])
        await client.publish('test/topic', b'my test message')
        await client.unsubscribe(['my/test/topic',])
        await client.disconnect()
        await asyncio.sleep(1)

        # get the plugin so it doesn't get gc on shutdown
        test_plugin = broker.plugins_manager.get_plugin('AllEventsPlugin')
        await broker.shutdown()
        await asyncio.sleep(1)

        assert all(test_plugin.test_flags.values()), f'event not received: {[event for event, value in test_plugin.test_flags.items() if not value]}'
