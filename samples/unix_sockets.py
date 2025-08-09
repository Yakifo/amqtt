import contextlib
import logging
import asyncio
from asyncio import StreamWriter, StreamReader, Event
from functools import partial

import typer

from amqtt.broker import Broker
from amqtt.client import ClientContext
from amqtt.contexts import ClientConfig, BrokerConfig, ListenerConfig, ListenerType
from amqtt.mqtt.protocol.client_handler import ClientProtocolHandler
from amqtt.plugins.manager import PluginManager
from amqtt.session import Session
from amqtt.adapters import ReaderAdapter, WriterAdapter

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


app = typer.Typer(add_completion=False, rich_markup_mode=None)

class UnixStreamReaderAdapter(ReaderAdapter):

    def __init__(self, reader: StreamReader):
        self._reader = reader

    async def read(self, n:int = -1) -> bytes:
        if n < 0:
            return await self._reader.read()
        return await self._reader.readexactly(n)

    def feed_eof(self):
        return self._reader.feed_eof()


class UnixStreamWriterAdapter(WriterAdapter):

    def __init__(self, writer: StreamWriter):
        self._writer = writer
        self.is_closed = Event()

    def write(self, data):
        if not self.is_closed.is_set():
            self._writer.write(data)

    async def drain(self):
        if self.is_closed.is_set():
            await self._writer.drain()

    def get_peer_info(self):
        extra_info = self._writer.get_extra_info('socket')
        return extra_info.getsockname(), 0

    async def close(self):
        if self.is_closed.is_set():
            return
        self.is_closed.set()

        await self._writer.drain()
        if self._writer.can_write_eof():
            self._writer.write_eof()

        self._writer.close()

        with contextlib.suppress(AttributeError):
            await self._writer.wait_closed()



async def run_broker():

    cfg = BrokerConfig(
        listeners={
            'default': ListenerConfig(
                type=ListenerType.EXTERNAL
            )
        },
        plugins={
            "amqtt.plugins.logging_amqtt.EventLoggerPlugin":{},
            "amqtt.plugins.logging_amqtt.PacketLoggerPlugin":{},
            "amqtt.plugins.authentication.AnonymousAuthPlugin":{"allow_anonymous":True},
        }
    )

    b = Broker(cfg)

    async def unix_stream_connected(reader, writer, listener_name):
        logger.info("received new unix connection....")
        r = UnixStreamReaderAdapter(reader)
        w = UnixStreamWriterAdapter(writer)
        await b.external_connected(reader=r, writer=w, listener_name='default')

    await asyncio.start_unix_server(partial(unix_stream_connected, listener_name='default'), path="/tmp/mqtt")
    await b.start()

    try:
        logger.info("starting mqtt unix server")
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await b.shutdown()

@app.command()
def broker():
    asyncio.run(run_broker())

async def run_client():
    config = ClientConfig()
    context = ClientContext()
    context.config = config
    plugins_manager = PluginManager("amqtt.client.plugins", context)

    cph = ClientProtocolHandler(plugins_manager)
    conn_reader, conn_writer = await asyncio.open_unix_connection(path="/tmp/mqtt")
    s = Session()
    s.client_id = "myUnixClientID"
    r = UnixStreamReaderAdapter(conn_reader)
    w = UnixStreamWriterAdapter(conn_writer)
    cph.attach(session=s, reader=r, writer=w)
    logger.debug("handler attached")
    ret = await cph.mqtt_connect()
    logger.info(f"client connected: {ret}")

    try:
        while True:
            await cph.mqtt_publish('my/topic', b'my message', 0, False)
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        cph.detach()

@app.command()
def client():
    asyncio.run(run_client())


if __name__ == "__main__":
    app()
