import asyncio
import logging

from amqtt.client import ClientError, MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2

#
# This sample shows how to subscbribe a topic and receive data from incoming messages
# It subscribes to '$SYS/broker/uptime' topic and displays the first ten values returned
# by the broker.
#

logger = logging.getLogger(__name__)


async def uptime_coro() -> None:
    C = MQTTClient()
    await C.connect("mqtt://test.mosquitto.org/")
    # Subscribe to '$SYS/broker/uptime' with QOS=1
    await C.subscribe(
        [
            ("$SYS/broker/uptime", QOS_1),
            ("$SYS/broker/load/#", QOS_2),
        ],
    )
    logger.info("Subscribed")
    try:
        for _i in range(1, 100):
            await C.deliver_message()
        await C.unsubscribe(["$SYS/broker/uptime", "$SYS/broker/load/#"])
        logger.info("UnSubscribed")
        await C.disconnect()
    except ClientError:
        logger.exception("Client exception")


if __name__ == "__main__":
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(uptime_coro())
