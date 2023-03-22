import logging
import asyncio

from amqtt_folder.client import MQTTClient, ClientException
from amqtt_folder.mqtt.constants import QOS_1, QOS_2, QOS_0


#
# This sample shows how to subscbribe a topic and receive data from incoming messages
# It subscribes to '$SYS/broker/uptime' topic and displays the first ten values returned
# by the broker.
#

logger = logging.getLogger(__name__)

config = {
    "keep_alive": 6000,
    "ping_delay": 1,
}
C = MQTTClient("Sub1client",config=config)

async def uptime_coro():
    #C = MQTTClient(config=config))
    try:
        await C.connect("mqtt://test:test@192.168.1.5:1883")
        # await C.connect("mqtt://192.168.1.5:1883")
        # Subscribe to '$SYS/broker/uptime' with QOS=1
        await C.subscribe(
            [
                ("a/b",1)
            ]
        )
    except ClientException as ce1:
            logger.error("Client exception: %s" % ce1)
    logger.info("Subscribed")
    try:
        for i in range(1, 100):
            message = await C.deliver_message()
            packet = message.publish_packet
            print(
                "%d: %s => %s"
                % (i, packet.variable_header.topic_name, str(packet.payload.data))
            )
        await C.unsubscribe(["tuple", "class"])
        logger.info("UnSubscribed")
        await C.disconnect()
    except ClientException as ce:
        logger.error("Client exception: %s" % ce)


if __name__ == "__main__":
    formatter = "[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    #logging.basicConfig(level=logging.INFO, format=formatter)
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    asyncio.get_event_loop().run_until_complete(uptime_coro())
