import asyncio
import logging
from importlib.metadata import EntryPoint
from unittest.mock import patch

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0

logger = logging.getLogger(__name__)

# test broker sys
@pytest.mark.asyncio
async def test_broker_sys_plugin() -> None:

    class MockEntryPoints:

        def select(self, group) -> list[EntryPoint]:
            match group:
                case 'tests.mock_plugins':
                    return [
                            EntryPoint(name='BrokerSysPlugin', group='tests.mock_plugins', value='amqtt.plugins.sys.broker:BrokerSysPlugin'),
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

        broker = Broker(plugin_namespace='tests.mock_plugins', config=config)
        await broker.start()
        client = MQTTClient()
        await client.connect("mqtt://127.0.0.1:1883/")
        await client.subscribe([("$SYS/broker/uptime", QOS_0),])
        await client.publish('test/topic', b'my test message')
        await asyncio.sleep(2)
        sys_msg_count = 0
        try:
            while True:
                message = await client.deliver_message(timeout_duration=1)
                if '$SYS' in message.topic:
                    sys_msg_count += 1
        except asyncio.TimeoutError:
            pass

        await client.disconnect()
        await broker.shutdown()

        assert sys_msg_count > 1
