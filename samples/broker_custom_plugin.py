import asyncio
from dataclasses import dataclass
import logging

from amqtt.broker import Broker
from amqtt.plugins.base import BasePlugin
from amqtt.session import Session

"""
This sample shows how to run a broker without stacktraces on keyboard interrupt
"""

logger = logging.getLogger(__name__)


class RemoteInfoPlugin(BasePlugin):

    async def on_broker_client_connected(self, *, client_id:str, client_session:Session) -> None:
        display_port_str = f"on port '{client_session.remote_port}'" if self.config.display_port else ""

        logger.info(f"client '{client_id}' connected from"
                    f" '{client_session.remote_address}' {display_port_str}")

    @dataclass
    class Config:
        display_port: bool = False

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
        "amqtt.plugins.authentication.AnonymousAuthPlugin": { "allow_anonymous": True},
        "samples.broker_custom_plugin.RemoteInfoPlugin": { "display_port": True },
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

async def main():
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
