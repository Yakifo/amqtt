import asyncio
import logging

from amqtt.client import ConnectError, MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2

"""
This sample shows how to publish messages to broker using different QOS
"""

logger = logging.getLogger(__name__)

config = {
    "will": {
        "topic": "/will/client",
        "message": b"Dead or alive",
        "qos": QOS_1,
        "retain": True,
    },
}


async def test_coro1() -> None:
    client = MQTTClient()
    await client.connect("mqtt://localhost:1883/")
    tasks = [
        asyncio.ensure_future(client.publish("a/b", b"TEST MESSAGE WITH QOS_0")),
        asyncio.ensure_future(client.publish("a/b", b"TEST MESSAGE WITH QOS_1", qos=QOS_1)),
        asyncio.ensure_future(client.publish("a/b", b"TEST MESSAGE WITH QOS_2", qos=QOS_2)),
    ]
    await asyncio.wait(tasks)
    logger.info("test_coro1 messages published")
    await client.disconnect()


async def test_coro2() -> None:
    try:
        client = MQTTClient(config={'auto_connect': False})
        await client.connect("mqtt://localhost:1884/")
        await client.publish("a/b", b"TEST MESSAGE WITH QOS_0", qos=0x00)
        await client.publish("a/b", b"TEST MESSAGE WITH QOS_1", qos=0x01)
        await client.publish("a/b", b"TEST MESSAGE WITH QOS_2", qos=0x02)
        logger.info("test_coro2 messages published")
        await client.disconnect()
    except ConnectError:
        logger.exception(f"Connection failed", exc_info=True)


def __main__():

    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)

    asyncio.run(test_coro1())
    asyncio.run(test_coro2())

if __name__ == "__main__":
    __main__()
