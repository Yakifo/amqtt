import asyncio
import logging

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0


logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_publish_to_dollar_sign_topics():
    """Applications cannot use a topic with a leading $ character for their own purposes."""

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
    try:
        msg = await c.deliver_message(timeout_duration=1)
        logger.debug(f"topic: {msg.topic}")
        assert msg is None
    except asyncio.TimeoutError:
        pass

    await c.disconnect()
    await asyncio.sleep(0.1)
    await b.shutdown()

@pytest.mark.asyncio
async def test_hash_will_not_receive_dollar():
    """A subscription to “#” will not receive any messages published to a topic beginning with a $"""

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

    try:
        msg = await c.deliver_message(timeout_duration=5)
        logger.debug(f"topic: {msg.topic}")
        assert msg is None
    except asyncio.TimeoutError:
        pass

    await c.disconnect()
    await asyncio.sleep(0.1)
    await b.shutdown()

# A subscription to “+/monitor/Clients” will not receive any messages published to “$SYS/monitor/Clients

# A subscription to “$SYS/#” will receive messages published to topics beginning with “$SYS/”

# A subscription to “$SYS/monitor/+” will receive messages published to “$SYS/monitor/Clients”

# For a Client to receive messages from topics that begin with $SYS/ and from topics that don’t begin with a $, it has to subscribe to both “#” and “$SYS/#”

