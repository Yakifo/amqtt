import logging
import asyncio

from hbmqtt.client import MQTTClient
from hbmqtt.mqtt.constants import QOS_1, QOS_2


#
# This sample shows how to publish messages to broker using different QOS
# Debug outputs shows the message flows
#

logger = logging.getLogger(__name__)

config = {
    "will": {
        "topic": "/will/client",
        "message": b"Dead or alive",
        "qos": 0x01,
        "retain": True,
    },
}
C = MQTTClient(config=config)
# C = MQTTClient()


async def test_coro():
    await C.connect("mqtts://test.mosquitto.org/", cafile="mosquitto.org.crt")
    tasks = [
        asyncio.ensure_future(C.publish("a/b", b"TEST MESSAGE WITH QOS_0")),
        asyncio.ensure_future(C.publish("a/b", b"TEST MESSAGE WITH QOS_1", qos=QOS_1)),
        asyncio.ensure_future(C.publish("a/b", b"TEST MESSAGE WITH QOS_2", qos=QOS_2)),
    ]
    await asyncio.wait(tasks)
    logger.info("messages published")
    await C.disconnect()


if __name__ == "__main__":
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    asyncio.get_event_loop().run_until_complete(test_coro())
