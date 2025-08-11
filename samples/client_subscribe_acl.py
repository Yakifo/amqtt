import asyncio
import logging

from amqtt.client import ClientError, MQTTClient
from amqtt.mqtt.constants import QOS_1

"""
Run `samples/broker_acl.py` or `samples/broker_taboo.py` 

This sample shows how to subscribe to different topics, some of which are allowed. 
"""

logger = logging.getLogger(__name__)


async def uptime_coro() -> None:
    client = MQTTClient()
    await client.connect("mqtt://test:test@0.0.0.0:1883")

    result = await client.subscribe(
        [
            ("$SYS/#", QOS_1),  # Topic forbidden when running `broker_acl.py`
            ("data/memes", QOS_1),  # Topic allowed
            ("data/classified", QOS_1),  # Topic forbidden
            ("repositories/amqtt/master", QOS_1),  # Topic allowed
            ("repositories/amqtt/devel", QOS_1),  # Topic forbidden when running `broker_acl.py`
            ("calendar/amqtt/releases", QOS_1),  # Topic allowed
        ],
    )
    logger.info(f"Subscribed results: {result}")
    try:
        for _i in range(1, 100):
            if msg := await client.deliver_message():
                logger.info(f"{msg.topic} >> {msg.data.decode()}")
        await client.unsubscribe(["$SYS/#", "data/memes"])
        logger.info("UnSubscribed")
        await client.disconnect()
    except ClientError:
        logger.exception("Client exception")


def __main__():
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(uptime_coro())

if __name__ == "__main__":
    __main__()
