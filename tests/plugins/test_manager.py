import asyncio
import logging
import unittest

from amqtt.events import BrokerEvents

from amqtt.plugins.base import BaseAuthPlugin, BaseTopicPlugin
from amqtt.plugins.manager import PluginManager
from amqtt.contexts import BaseContext, Action
from amqtt.session import Session

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=formatter)


class EmptyTestPlugin:
    def __init__(self, context: BaseContext) -> None:
        self.context = context


class EventTestPlugin(BaseAuthPlugin, BaseTopicPlugin):
    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)
        self.test_close_flag = False
        self.test_auth_flag = False
        self.test_topic_flag = False
        self.test_event_flag = False

    async def on_broker_message_received(self) -> None:
        self.test_event_flag = True

    async def authenticate(self, *, session: Session) -> bool | None:
        self.test_auth_flag = True
        return None

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool:
        self.test_topic_flag = True
        return False

    async def close(self) -> None:
        self.test_close_flag = True


class TestPluginManager(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()

    def test_load_plugin(self) -> None:
        manager = PluginManager("amqtt.test.plugins", context=None)
        assert len(manager._plugins) > 0

    def test_fire_event(self) -> None:
        async def fire_event() -> None:
            await manager.fire_event(BrokerEvents.MESSAGE_RECEIVED)
            await asyncio.sleep(1)
            await manager.close()

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(fire_event())
        plugin = manager.get_plugin("EventTestPlugin")
        assert plugin is not None
        assert plugin.test_event_flag

    def test_fire_event_wait(self) -> None:
        async def fire_event() -> None:
            await manager.fire_event(BrokerEvents.MESSAGE_RECEIVED, wait=True)
            await manager.close()

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(fire_event())
        plugin = manager.get_plugin("EventTestPlugin")
        assert plugin is not None
        assert plugin.test_event_flag

    def test_plugin_close_coro(self) -> None:

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(manager.map_plugin_close())
        self.loop.run_until_complete(asyncio.sleep(0.5))
        plugin = manager.get_plugin("EventTestPlugin")
        assert plugin is not None
        assert plugin.test_close_flag

    def test_plugin_auth_coro(self) -> None:

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(manager.map_plugin_auth(session=Session()))
        self.loop.run_until_complete(asyncio.sleep(0.5))
        plugin = manager.get_plugin("EventTestPlugin")
        assert plugin is not None
        assert plugin.test_auth_flag

    def test_plugin_topic_coro(self) -> None:

        manager = PluginManager("amqtt.test.plugins", context=None)
        self.loop.run_until_complete(manager.map_plugin_topic(session=Session(), topic="test", action=Action.PUBLISH))
        self.loop.run_until_complete(asyncio.sleep(0.5))
        plugin = manager.get_plugin("EventTestPlugin")
        assert plugin is not None
        assert plugin.test_topic_flag
