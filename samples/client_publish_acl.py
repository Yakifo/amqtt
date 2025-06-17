import asyncio
import logging

from amqtt.client import ConnectError, MQTTClient
from amqtt.mqtt.constants import QOS_1

"""
This sample shows how to publish messages to broker running either `samples/broker_acl.py`
 or `samples/broker_taboo.py`. 
"""

logger = logging.getLogger(__name__)


async def test_coro() -> None:
    try:
        client = MQTTClient()
        await client.connect("mqtt://0.0.0.0:1883")
        await client.publish("data/classified", b"TOP SECRET", qos=QOS_1)
        await client.publish("data/memes", b"REAL FUN", qos=QOS_1)
        await client.publish("repositories/amqtt/master", b"NEW STABLE RELEASE", qos=QOS_1)
        await client.publish(
            "repositories/amqtt/devel",
            b"THIS NEEDS TO BE CHECKED",
            qos=QOS_1,
        )
        await client.publish("calendar/amqtt/releases", b"NEW RELEASE", qos=QOS_1)
        logger.info("messages published")
        await client.disconnect()
    except ConnectError as ce:
        logger.exception("ERROR: Connection failed")


def __main__():

    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)

    asyncio.run(test_coro())

if __name__ == "__main__":
    __main__()
