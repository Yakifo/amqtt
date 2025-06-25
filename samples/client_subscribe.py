import asyncio
import logging

from amqtt.client import ClientError, MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2


"""
This sample shows how to subscribe to different $SYS topics and how to receive incoming messages 
"""

logger = logging.getLogger(__name__)


async def uptime_coro() -> None:
    client = MQTTClient()
    await client.connect("mqtt://test.mosquitto.org/")

    await client.subscribe(
        [
            ("$SYS/broker/uptime", QOS_1),
            ("$SYS/broker/load/#", QOS_2),
        ],
    )
    logger.info("Subscribed")
    try:
        for _i in range(1, 10):
            if msg := await client.deliver_message():
                logger.info(f"{msg.topic} >> {msg.data.decode()}")
        await client.unsubscribe(["$SYS/broker/uptime", "$SYS/broker/load/#"])
        logger.info("UnSubscribed")
        await client.disconnect()
    except ClientError:
        logger.exception("Client exception")


def __main__():
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.run(uptime_coro())

if __name__ == "__main__":
    __main__()
