import asyncio
import logging

from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2

"""
This sample shows how to publish messages to secure websocket broker 
"""

logger = logging.getLogger(__name__)

config = {
    "will": {
        "topic": "/will/client",
        "message": "Dead or alive",
        "qos": QOS_1,
        "retain": True,
    }
}
client = MQTTClient(config=config)


async def test_coro() -> None:
    await client.connect("ws://localhost:8080/")
    tasks = [
        asyncio.ensure_future(client.publish("a/b", b"TEST MESSAGE WITH QOS_0")),
        asyncio.ensure_future(client.publish("a/b", b"TEST MESSAGE WITH QOS_1", qos=QOS_1)),
        asyncio.ensure_future(client.publish("a/b", b"TEST MESSAGE WITH QOS_2", qos=QOS_2)),
    ]
    await asyncio.wait(tasks)
    logger.info("messages published")
    await client.disconnect()


def __main__():
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    asyncio.run(test_coro())

if __name__ == "__main__":
    __main__()
