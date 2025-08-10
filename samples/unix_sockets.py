import contextlib
import logging
import asyncio
import ssl
from asyncio import StreamWriter, StreamReader, Event
from functools import partial
from pathlib import Path

import typer

from amqtt.broker import Broker
from amqtt.client import ClientContext
from amqtt.contexts import ClientConfig, BrokerConfig, ListenerConfig, ListenerType
from amqtt.mqtt.protocol.client_handler import ClientProtocolHandler
from amqtt.plugins.manager import PluginManager
from amqtt.session import Session
from amqtt.adapters import ReaderAdapter, WriterAdapter

logger = logging.getLogger(__name__)


app = typer.Typer(add_completion=False, rich_markup_mode=None)

#   Usage: unix_sockets.py [OPTIONS] COMMAND [ARGS]...
#
#   Options:
#     --help  Show this message and exit.
#
#  Commands:
#     broker  Run an mqtt broker that communicates over a unix (file) socket.
#     client  Run an mqtt client that communicates over a unix (file) socket.


class UnixStreamReaderAdapter(ReaderAdapter):

    def __init__(self, reader: StreamReader) -> None:
        self._reader = reader

    async def read(self, n:int = -1) -> bytes:
        if n < 0:
            return await self._reader.read()
        return await self._reader.readexactly(n)

    def feed_eof(self) -> None:
        return self._reader.feed_eof()


class UnixStreamWriterAdapter(WriterAdapter):

    def __init__(self, writer: StreamWriter) -> None:
        self._writer = writer
        self.is_closed = Event()

    def write(self, data: bytes) -> None:
        if not self.is_closed.is_set():
            self._writer.write(data)

    async def drain(self) -> None:
        if self.is_closed.is_set():
            await self._writer.drain()

    def get_peer_info(self) -> tuple[str, int]:
        extra_info = self._writer.get_extra_info('socket')
        return extra_info.getsockname(), 0

    async def close(self) -> None:
        if self.is_closed.is_set():
            return
        self.is_closed.set()

        await self._writer.drain()
        if self._writer.can_write_eof():
            self._writer.write_eof()

        self._writer.close()

        with contextlib.suppress(AttributeError):
            await self._writer.wait_closed()

    def get_ssl_info(self) -> ssl.SSLObject | None:
        pass


async def run_broker(socket_file: Path):

    # configure the broker with a single, external listener
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

    # new connection handler
    async def unix_stream_connected(reader: StreamReader, writer: StreamWriter, listener_name: str):
        logger.info("received new unix connection....")
        # wraps the reader/writer in a compatible interface
        r = UnixStreamReaderAdapter(reader)
        w = UnixStreamWriterAdapter(writer)

        # passes the connection to the broker for protocol communications
        await b.external_connected(reader=r, writer=w, listener_name=listener_name)

    await asyncio.start_unix_server(partial(unix_stream_connected, listener_name='default'), path=socket_file)
    await b.start()

    try:
        logger.info("starting mqtt unix server")
        # run until ctrl-c
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await b.shutdown()


@app.command()
def broker(
        socket_file: str | None = typer.Option("/tmp/mqtt", "-s", "--socket", help="path and file for unix socket"),
        verbose: bool = typer.Option(False, "-v", "--verbose", help="set logging level to DEBUG"),
):
    """Run an mqtt broker that communicates over a unix (file) socket."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    asyncio.run(run_broker(Path(socket_file)))


async def run_client(socket_file: Path):
    # 'MQTTClient' establishes the connection but uses the ClientProtocolHandler for MQTT protocol communications

    # create a plugin manager
    config = ClientConfig()
    context = ClientContext()
    context.config = config
    plugins_manager = PluginManager("amqtt.client.plugins", context)

    # create a client protocol handler
    cph = ClientProtocolHandler(plugins_manager)

    # connect to the unix socket
    conn_reader, conn_writer = await asyncio.open_unix_connection(path=socket_file)

    # anonymous session connection just needs a client_id
    s = Session()
    s.client_id = "myUnixClientID"

    # wraps the reader/writer in compatible interface
    r = UnixStreamReaderAdapter(conn_reader)
    w = UnixStreamWriterAdapter(conn_writer)

    # pass the connection to the protocol handler for mqtt communications and initiate CONNECT/CONNACK
    cph.attach(session=s, reader=r, writer=w)
    logger.debug("handler attached")
    ret = await cph.mqtt_connect()
    logger.info(f"client connected: {ret}")

    try:
        while True:
            # periodically send a message
            await cph.mqtt_publish('my/topic', b'my message', 0, False)
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        cph.detach()


@app.command()
def client(
    socket_file: str | None = typer.Option("/tmp/mqtt", "-s", "--socket", help="path and file for unix socket"),
        verbose: bool = typer.Option(False, "-v", "--verbose", help="set logging level to DEBUG"),
):
    """Run an mqtt client that communicates over a unix (file) socket."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    asyncio.run(run_client(Path(socket_file)))


if __name__ == "__main__":
    app()
