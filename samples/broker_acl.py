import asyncio
import logging
import os
from pathlib import Path

from amqtt.broker import Broker

"""
This sample shows how to run a broker with the topic check acl plugin
"""

logger = logging.getLogger(__name__)

config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        },
        "ws-mqtt": {
            "bind": "127.0.0.1:8080",
            "type": "ws",
            "max_connections": 10,
        },
    },
    "plugins": {
        'amqtt.plugins.authentication.AnonymousAuthPlugin': { 'allow_anonymous': True},
        'amqtt.plugins.authentication.FileAuthPlugin': {
            'password_file': Path(__file__).parent / 'passwd',
        },
        'amqtt.plugins.sys.broker.BrokerSysPlugin': { "sys_interval": 10},
        'amqtt.plugins.topic_checking.TopicAccessControlListPlugin': {
            'acl': {
                # username: [list of allowed topics]
                "test": ["repositories/+/master", "calendar/#", "data/memes"],
                "anonymous": [],
            }
        }
    }
}


async def main_loop():
    broker = Broker(config)
    try:
        await broker.start()
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await broker.shutdown()


async def main() -> None:
    t = asyncio.create_task(main_loop())
    try:
        await t
    except asyncio.CancelledError:
        pass


def __main__():
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    task = loop.create_task(main())

    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping server...")
        task.cancel()
        loop.run_until_complete(task)  # Ensure task finishes cleanup
    finally:
        logger.info("Server stopped.")
        loop.close()

if __name__ == "__main__":
    __main__()
