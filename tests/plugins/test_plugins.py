import inspect
from importlib.metadata import EntryPoint
from logging import getLogger
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

import amqtt.plugins
from amqtt.broker import Broker, BrokerContext
from amqtt.errors import PluginError, PluginInitError, PluginImportError
from amqtt.plugins.base import BasePlugin
from amqtt.plugins.manager import BaseContext

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
