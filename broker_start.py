import logging
import asyncio
import os
from amqtt_folder.broker import Broker


logger = logging.getLogger(__name__)

config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
             "max-connections": 50000
        },
    },
    "sys_interval": 6000,
    "auth": {
        "allow-anonymous": True,
        "password-file": os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "passwd"
        ),
        "plugins": ["auth_file", "auth_anonymous"],
    },
    "topic-check": {
        "enabled": True,
        "plugins": ["topic_acl"] ,
        "acl": {
            "test": ["a/#"],
            "testpub1": ["a/b"],
            "anonymous":["#"]
            },
    },
}

broker = Broker(config)


async def test_coro():
    await broker.start()
    # await asyncio.sleep(5)
    # await broker.shutdown()


if __name__ == "__main__":
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    # formatter = "%(asctime)s :: %(levelname)s :: %(message)s"
    #logging.basicConfig(level=logging.INFO, format=formatter)
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    asyncio.get_event_loop().run_until_complete(test_coro())
    asyncio.get_event_loop().run_forever()
