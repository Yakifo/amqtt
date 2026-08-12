import asyncio
from dataclasses import dataclass
import logging

from amqtt.broker import Broker
from amqtt.plugins.base import BasePlugin
from amqtt.session import Session, ApplicationMessage

"""
This sample shows how to run a broker without stacktraces on keyboard interrupt
"""

logger = logging.getLogger(__name__)


class ClientDollarBroadcast(BasePlugin):

    async def _broadcast_sys_topic(self, topic_basename: str, data: bytes) -> None:
        """Broadcast a system topic."""
    async def on_broker_message_received(self, *, client_id: str, message: ApplicationMessage) -> None:
        """typically, MQTT-4.7.2-1 blocks clients from sending `$` messages, example how to bypass"""
        if message.topic.startswith("$"):
            await self.context.broadcast_message(message.topic, message.data, message.qos)

            # spec doesn't define if we're required to retain `$` topic messages, so this is optional
            if message.publish_packet and message.publish_packet.retain_flag:
                await self.context.retain_message(message.topic, message.data, message.qos)


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
        "samples.broker_dollar_topics.ClientDollarBroadcast": { },
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
