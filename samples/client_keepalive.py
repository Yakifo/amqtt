import asyncio
import logging
from asyncio import CancelledError

from amqtt.client import MQTTClient

"""
This sample shows how to run an idle client
"""

logger = logging.getLogger(__name__)

config = {
    "keep_alive": 5,
    "ping_delay": 1,
}

async def main() -> None:
    client = MQTTClient(config=config)

    try:
        await client.connect("mqtt://localhost:1883/")
        logger.info("client connected")
        await asyncio.sleep(15)
    except CancelledError:
        pass

    await client.disconnect()


def __main__():

    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.run(main())


if __name__ == "__main__":
    __main__()
