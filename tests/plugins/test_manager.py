import asyncio
import logging
from typing import Any
import unittest

from amqtt.plugins.manager import BaseContext, Plugin, PluginManager

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=formatter)


class EmptyTestPlugin:
    def __init__(self, context: BaseContext) -> None:
        self.context = context


class EventTestPlugin:
    def __init__(self, context: BaseContext) -> None:
        self.context = context
        self.test_flag = False
        self.coro_flag = False

    async def on_test(self) -> None:
        self.test_flag = True
        self.context.logger.info("on_test")

    async def test_coro(self) -> None:
        self.coro_flag = True

    async def ret_coro(self) -> str:
        return "TEST"


class TestPluginManager(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()

    def test_load_plugin(self) -> None:
        manager = PluginManager("amqtt.test.plugins", context=None)
        assert len(manager._plugins) > 0

    def test_fire_event(self) -> None:
        async def fire_event() -> None:
            await manager.fire_event("test")
            await asyncio.sleep(1)
            await manager.close()

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(fire_event())
        plugin = manager.get_plugin("event_plugin")
        assert plugin is not None
        assert plugin.object.test_flag

    def test_fire_event_wait(self) -> None:
        async def fire_event() -> None:
            await manager.fire_event("test", wait=True)
            await manager.close()

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(fire_event())
        plugin = manager.get_plugin("event_plugin")
        assert plugin is not None
        assert plugin.object.test_flag

    def test_map_coro(self) -> None:
        async def call_coro() -> None:
            await manager.map_plugin_coro("test_coro")

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(call_coro())
        plugin = manager.get_plugin("event_plugin")
        assert plugin is not None
        assert plugin.object.test_coro

    def test_map_coro_return(self) -> None:
        async def call_coro() -> dict[Plugin, str]:
            return await manager.map_plugin_coro("ret_coro")

        manager = PluginManager("amqtt.test.plugins", context=None)
        ret = self.loop.run_until_complete(call_coro())
        plugin = manager.get_plugin("event_plugin")
        assert plugin is not None
        assert ret[plugin] == "TEST"

    def test_map_coro_filter(self) -> None:
        """Run plugin coro but expect no return as an empty filter is given."""

        async def call_coro() -> dict[Plugin, Any]:
            return await manager.map_plugin_coro("ret_coro", filter_plugins=[])

        manager = PluginManager("amqtt.test.plugins", context=None)
        ret = self.loop.run_until_complete(call_coro())
        assert len(ret) == 0
