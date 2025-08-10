import argparse
import asyncio
import logging

from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2

"""
This sample shows how to publish messages to secure broker.

Use `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem -subj "/CN=localhost"` to
generate a self-signed certificate for the broker to use.
"""

logger = logging.getLogger(__name__)

config = {
    "will": {
        "topic": "/will/client",
        "message": "Dead or alive",
        "qos": QOS_1,
        "retain": True,
    },
    "auto_reconnect": False,
    "check_hostname": False,
    "certfile": "",
}


async def test_coro(certfile: str) -> None:
    config["certfile"] = certfile
    client = MQTTClient(config=config)

    await client.connect("mqtts://localhost:8883")
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert", default="cert.pem", help="path & file to verify server's authenticity")
    args = parser.parse_args()

    asyncio.run(test_coro(args.cert))

if __name__ == "__main__":
    __main__()
