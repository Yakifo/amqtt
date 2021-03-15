import logging
import asyncio

from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_1


#
# This sample shows how to subscbribe a topic and receive data from incoming messages
# It subscribes to '$SYS/broker/uptime' topic and displays the first ten values returned
# by the broker.
#

logger = logging.getLogger(__name__)


async def uptime_coro():
    C = MQTTClient()
    await C.connect("mqtt://test:test@0.0.0.0:1883")
    # await C.connect('mqtt://0.0.0.0:1883')
    # Subscribe to '$SYS/broker/uptime' with QOS=1
    await C.subscribe(
        [
            ("data/memes", QOS_1),  # Topic allowed
            ("data/classified", QOS_1),  # Topic forbidden
            ("repositories/hbmqtt/master", QOS_1),  # Topic allowed
            ("repositories/hbmqtt/devel", QOS_1),  # Topic forbidden
            ("calendar/hbmqtt/releases", QOS_1),  # Topic allowed
        ]
    )
    logger.info("Subscribed")
    try:
        for i in range(1, 100):
            message = await C.deliver_message()
            packet = message.publish_packet
            print(
                "%d: %s => %s"
                % (i, packet.variable_header.topic_name, str(packet.payload.data))
            )
        await C.unsubscribe(["$SYS/broker/uptime", "$SYS/broker/load/#"])
        logger.info("UnSubscribed")
        await C.disconnect()
    except ClientException as ce:
        logger.error("Client exception: %s" % ce)


if __name__ == "__main__":
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(uptime_coro())
