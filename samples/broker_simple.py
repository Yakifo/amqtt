import asyncio
import logging

from amqtt.broker import Broker

broker = Broker()


async def test_coro() -> None:
    await broker.start()


if __name__ == "__main__":
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)

    asyncio.get_event_loop().run_until_complete(test_coro())
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        asyncio.get_event_loop().run_until_complete(broker.shutdown())
