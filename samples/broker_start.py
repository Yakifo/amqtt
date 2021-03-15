import logging
import asyncio
import os
from hbmqtt.broker import Broker

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
    "sys_interval": 10,
    "auth": {
        "allow-anonymous": True,
        "password-file": os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "passwd"
        ),
        "plugins": ["auth_file", "auth_anonymous"],
    },
    "topic-check": {"enabled": False},
}

broker = Broker(config)


async def test_coro():
    await broker.start()
    # await asyncio.sleep(5)
    # await broker.shutdown()


if __name__ == "__main__":
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    # formatter = "%(asctime)s :: %(levelname)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    asyncio.get_event_loop().run_until_complete(test_coro())
    asyncio.get_event_loop().run_forever()
