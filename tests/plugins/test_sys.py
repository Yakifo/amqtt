import asyncio
import logging
from importlib.metadata import EntryPoint
from logging.config import dictConfig
from unittest.mock import patch

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0

dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'verbose',
        }
    },
    'loggers': {
        'transitions': {
            'level': 'WARNING',
        }
    }
})

# logging.basicConfig(level=logging.DEBUG, format=formatter)

logger = logging.getLogger(__name__)



all_sys_topics = [
    '$SYS/broker/version',
    '$SYS/broker/load/bytes/received',
    '$SYS/broker/load/bytes/sent',
    '$SYS/broker/messages/received',
    '$SYS/broker/messages/sent',
    '$SYS/broker/time',
    '$SYS/broker/uptime',
    '$SYS/broker/uptime/formatted',
    '$SYS/broker/clients/connected',
    '$SYS/broker/clients/disconnected',
    '$SYS/broker/clients/maximum',
    '$SYS/broker/clients/total',
    '$SYS/broker/messages/inflight',
    '$SYS/broker/messages/inflight/in',
    '$SYS/broker/messages/inflight/out',
    '$SYS/broker/messages/inflight/stored',
    '$SYS/broker/messages/publish/received',
    '$SYS/broker/messages/publish/sent',
    '$SYS/broker/messages/retained/count',
    '$SYS/broker/messages/subscriptions/count',
    '$SYS/broker/heap/size',
    '$SYS/broker/heap/maximum',
    '$SYS/broker/cpu/percent',
    '$SYS/broker/cpu/maximum',
]



# test broker sys
@pytest.mark.asyncio
async def test_broker_sys_plugin_deprecated_config() -> None:

    sys_topic_flags = {sys_topic:False for sys_topic in all_sys_topics}

    class MockEntryPoints:

        def select(self, group) -> list[EntryPoint]:
            match group:
                case 'tests.mock_plugins':
                    return [
                            EntryPoint(name='broker_sys', group='tests.mock_plugins', value='amqtt.plugins.sys.broker:BrokerSysPlugin'),
                            EntryPoint(name='auth_anonymous', group='test.mock_plugins', value='amqtt.plugins.authentication:AnonymousAuthPlugin'),
                        ]
                case _:
                    return list()


    with patch("amqtt.plugins.manager.entry_points", side_effect=MockEntryPoints) as mocked_mqtt_publish:

        config = {
            "listeners": {
                "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
            },
            'sys_interval': 1,
            'auth': {
                'allow_anonymous': True
            }
        }

        broker = Broker(plugin_namespace='tests.mock_plugins', config=config)
        await broker.start()
        client = MQTTClient()
        await client.connect("mqtt://127.0.0.1:1883/")
        await client.subscribe([("$SYS/#", QOS_0),])
        await client.publish('test/topic', b'my test message')
        await asyncio.sleep(2)
        sys_msg_count = 0
        try:
            while sys_msg_count < 30:
                message = await client.deliver_message(timeout_duration=1)
                if '$SYS' in message.topic:
                    sys_msg_count += 1
                    assert message.topic in sys_topic_flags
                    sys_topic_flags[message.topic] = True

        except asyncio.TimeoutError:
            logger.debug(f"TimeoutError after {sys_msg_count} messages")

        await client.disconnect()
        await broker.shutdown()

        assert sys_msg_count > 1

        assert all(sys_topic_flags.values()), f'topic not received: {[ topic for topic, flag in sys_topic_flags.items() if not flag ]}'


@pytest.mark.asyncio
async def test_broker_sys_plugin_config() -> None:

    sys_topic_flags = {sys_topic:False for sys_topic in all_sys_topics}

    config = {
        "listeners": {
            "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        },
        'plugins': [
            {'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': True}},
            {'amqtt.plugins.sys.broker.BrokerSysPlugin': {'sys_interval': 1}},
        ]
    }

    broker = Broker(plugin_namespace='tests.mock_plugins', config=config)
    await broker.start()
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1:1883/")
    await client.subscribe([("$SYS/#", QOS_0), ])
    await client.publish('test/topic', b'my test message')
    await asyncio.sleep(2)
    sys_msg_count = 0
    try:
        while sys_msg_count < 30:
            message = await client.deliver_message(timeout_duration=1)
            if '$SYS' in message.topic:
                sys_msg_count += 1
                assert message.topic in sys_topic_flags
                sys_topic_flags[message.topic] = True

    except asyncio.TimeoutError:
        logger.debug(f"TimeoutError after {sys_msg_count} messages")

    await client.disconnect()
    await broker.shutdown()

    assert sys_msg_count > 1

    assert all(
        sys_topic_flags.values()), f'topic not received: {[topic for topic, flag in sys_topic_flags.items() if not flag]}'
