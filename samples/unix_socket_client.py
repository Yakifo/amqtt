import asyncio

from amqtt.client import MQTTClient, ClientContext
from amqtt.contexts import ClientConfig
from amqtt.mqtt.protocol.client_handler import ClientProtocolHandler
from amqtt.plugins.manager import PluginManager
from amqtt.session import Session
from samples.unix_socket_adapters import UnixStreamReaderAdapter, UnixStreamWriterAdapter


async def client():
    config = ClientConfig()
    context = ClientContext()
    context.config = config
    plugins_manager = PluginManager("amqtt.client.plugins", context)

    cph = ClientProtocolHandler(plugins_manager)

    s = Session()
    r = UnixStreamReaderAdapter()
    w = UnixStreamWriterAdapter()

    cph.attach(session=s, reader=r, writer=w)
    await cph.mqtt_connect()

if __name__ == '__main__':
    asyncio.run(client())
