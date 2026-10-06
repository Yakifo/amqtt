import asyncio
from dataclasses import dataclass
import logging

from amqtt.broker import Broker
from amqtt.mqtt import MQTTPacket, ConnectPacket
from amqtt.mqtt.packet import MQTTVariableHeader, MQTTPayload, MQTTFixedHeader
from amqtt.plugins.base import BasePlugin
from amqtt.session import Session

"""
This sample shows how to create a broker plugin which reports on all client connection request issues.
"""

logger = logging.getLogger(__name__)


class ConnectPacketInfoPlugin(BasePlugin):

    async def on_mqtt_packet_received(self, *,
                                      packet: MQTTPacket[MQTTVariableHeader, MQTTPayload[MQTTVariableHeader], MQTTFixedHeader],
                                      session: Session | None = None) -> None:
        if not isinstance(packet, ConnectPacket):
            return

        msg = []

        if packet.proto_name != "MQTT":
            msg.append(f"incorrect protocol name [{packet.proto_name}] (must be MQTT)")

        if packet.proto_level != 4:
            msg.append(f"incorrect protocol level [{packet.proto_level}] (must be 4)")

        if msg:
            logger.info(f"Client {packet.client_id} had invalid connection: {', '.join(msg)}")

    @dataclass
    class Config:
        pass

config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        }
    },
    "plugins": {
        "amqtt.plugins.authentication.AnonymousAuthPlugin": { "allow_anonymous": True},
        "samples.broker_connect_info_plugin.ConnectPacketInfoPlugin": {  },
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
