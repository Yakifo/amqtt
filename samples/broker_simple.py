import asyncio
from asyncio import CancelledError
import logging

from amqtt.broker import Broker

"""
This sample shows how to run a broker
"""

formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
logging.basicConfig(level=logging.INFO, format=formatter)


async def run_server() -> None:
    broker = Broker()
    try:
        await broker.start()
        while True:
            await asyncio.sleep(1)
    except CancelledError:
        await broker.shutdown()

def __main__():
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("Server exiting...")

if __name__ == "__main__":
    __main__()
