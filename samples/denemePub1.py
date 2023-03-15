import logging
import asyncio

from amqtt.client import MQTTClient, ConnectException
from amqtt.mqtt.constants import QOS_1, QOS_2


#
# This sample shows how to publish messages to broker using different QOS
# Debug outputs shows the message flows
#

logger = logging.getLogger(__name__)

config = {
    "keep_alive": 6000,
    "ping_delay": 1,
    "will": {
        "topic": "/will/client",
        "message": b"Dead or alive",
        "qos": 0x01,
        "retain": True,
    }
}


async def test_coro():
    C = MQTTClient("pub1client",config=config)
    await C.connect("mqtt://test:test@192.168.1.5:1883")
    tasks = [
        asyncio.ensure_future(C.publish("a/b", b"TEST MESSAGE WITH QOS_0")),
        asyncio.ensure_future(C.publish("a/b", b"TEST MESSAGE WITH QOS_1", qos=QOS_1)),
        asyncio.ensure_future(C.publish("a/b", b"TEST MESSAGE WITH QOS_2", qos=QOS_2)),
    ]
    await asyncio.wait(tasks)
    logger.info("messages published")
    await C.disconnect()


async def test_coro2():
    try:
        C = MQTTClient("pub1client",config=config)
        #await C.connect("mqtt://testpub1:test@192.168.1.5:1883")
        await C.connect("mqtt://192.168.1.5:1883")
        #await C.publish("a/b", b"TEST MESSAGE WITH QOS_0", qos=0x00)
        await C.publish("a/b", b"TEST MESSAGE WITH QOS_1", qos=0x01)
        #await C.publish("a/b", b"TEST MESSAGE WITH QOS_2", qos=0x02)
        logger.info("messages published")
        # await C.disconnect()
    except ConnectException as ce:
        logger.error("Connection failed: %s" % ce)
        asyncio.get_event_loop().stop()

    try:
        for i in range(1, 100):
            message = await C.deliver_message()
            packet = message.publish_packet
            print(
                "%d: %s => %s"
                % (i, packet.variable_header.topic_name, str(packet.payload.data))
            )

    except ClientException as ce2:
        logger.error("Client exception: %s" % ce2)


if __name__ == "__main__":
    formatter = (
        "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    )
    formatter = "%(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    #asyncio.get_event_loop().run_until_complete(test_coro())
    asyncio.get_event_loop().run_until_complete(test_coro2())
