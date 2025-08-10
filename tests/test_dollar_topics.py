import asyncio
import logging

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt3.constants import QOS_0


logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_publish_to_dollar_sign_topics():
    """Applications cannot use a topic with a leading $ character for their own purposes [MQTT-4.7.2-1]."""

    cfg = {
        'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1'}},
        'plugins': {'amqtt.plugins.authentication.AnonymousAuthPlugin': {"allow_anonymous": True}},
    }

    b = Broker(config=cfg)
    await b.start()
    await asyncio.sleep(0.1)
    c = MQTTClient(config={'auto_reconnect': False})
    await c.connect()
    await asyncio.sleep(0.1)
    await c.subscribe(
        [('$#', QOS_0),
         ('#', QOS_0)]
    )
    await asyncio.sleep(0.1)
    await c.publish('$MY', b'message should be blocked')
    await asyncio.sleep(0.1)

    with pytest.raises(asyncio.TimeoutError):
        # wait long enough for broker sys plugin to run
        _ = await c.deliver_message(timeout_duration=1)

    await c.disconnect()
    await asyncio.sleep(0.1)
    await b.shutdown()

@pytest.mark.asyncio
async def test_hash_will_not_receive_dollar():
    """A subscription to “#” will not receive any messages published to a topic beginning with a $ [MQTT-4.7.2-1]."""

    cfg = {
        'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1'}},
        'plugins': {
            'amqtt.plugins.authentication.AnonymousAuthPlugin': {"allow_anonymous": True},
            'amqtt.plugins.sys.broker.BrokerSysPlugin': {"sys_interval": 2}
        }
    }

    b = Broker(config=cfg)
    await b.start()
    await asyncio.sleep(0.1)
    c = MQTTClient(config={'auto_reconnect': False})
    await c.connect()
    await asyncio.sleep(0.1)
    await c.subscribe(
        [('#', QOS_0)]
    )
    await asyncio.sleep(0.1)

    with pytest.raises(asyncio.TimeoutError):
        # wait long enough for broker sys plugin to run
        _ = await c.deliver_message(timeout_duration=5)

    await c.disconnect()
    await asyncio.sleep(0.1)
    await b.shutdown()


@pytest.mark.asyncio
async def test_plus_will_not_receive_dollar():
    """A subscription to “+/monitor/Clients” will not receive any messages published to “$SYS/monitor/Clients [MQTT-4.7.2-1]"""
    # BrokerSysPlugin doesn't use $SYS/monitor/Clients, so this is an equivalent test with $SYS/broker topics

    cfg = {
        'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1'}},
        'plugins': {
            'amqtt.plugins.authentication.AnonymousAuthPlugin': {"allow_anonymous": True},
            'amqtt.plugins.sys.broker.BrokerSysPlugin': {"sys_interval": 2}
        }
    }

    b = Broker(config=cfg)
    await b.start()
    await asyncio.sleep(0.1)
    c = MQTTClient(config={'auto_reconnect': False})
    await c.connect()
    await asyncio.sleep(0.1)
    await c.subscribe(
        [('+/broker/#', QOS_0),
         ('+/broker/time', QOS_0),
         ('+/broker/clients/#', QOS_0),
         ('+/broker/+/maximum', QOS_0)
         ]
    )
    await asyncio.sleep(0.1)

    with pytest.raises(asyncio.TimeoutError):
        # wait long enough for broker sys plugin to run
        _ = await c.deliver_message(timeout_duration=5)

    await c.disconnect()
    await asyncio.sleep(0.1)
    await b.shutdown()
