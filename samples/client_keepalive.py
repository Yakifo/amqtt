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
        await client.connect("mqtt://test.mosquitto.org:1883/")
        logger.info("client connected")
        await asyncio.sleep(18)
    except CancelledError:
        pass

    await client.disconnect()


def __main__():

    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    task = loop.create_task(main())

    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping client...")
        task.cancel()
        loop.run_until_complete(task)  # Ensure task finishes cleanup
    finally:

        loop.close()

if __name__ == "__main__":
    __main__()
