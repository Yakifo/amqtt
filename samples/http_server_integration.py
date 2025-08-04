import asyncio
import io
import logging

import aiohttp
from aiohttp import web

from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig, ListenerConfig, ListenerType
from amqtt.errors import ConnectError

logger = logging.getLogger(__name__)

MQTT_LISTENER_NAME = "myMqttListener"

async def hello(request):
    """get request handler"""
    return web.Response(text="Hello, world")

class WebSocketResponseReader(ReaderAdapter):
    """Interface to allow mqtt broker to read from an aiohttp websocket connection."""

    def __init__(self, ws: web.WebSocketResponse):
        self.ws = ws
        self.buffer = bytearray()

    async def read(self, n: int = -1) -> bytes:
        """
        read 'n' bytes from the datastream, if < 0 read all available bytes

        Raises:
            BrokerPipeError : if reading on a closed websocket connection
        """
        # continue until buffer contains at least the amount of data being requested
        while not self.buffer or len(self.buffer) < n:
            # if the websocket is closed
            if self.ws.closed:
                raise BrokenPipeError()

            try:
                # read from stream
                msg = await asyncio.wait_for(self.ws.receive(), timeout=0.5)
                # mqtt streams should always be binary...
                if msg.type == aiohttp.WSMsgType.BINARY:
                    self.buffer.extend(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    raise BrokenPipeError()

            except asyncio.TimeoutError:
                raise BrokenPipeError()

        # return all bytes currently in the buffer
        if n == -1:
            result = bytes(self.buffer)
            self.buffer.clear()
        # return the requested number of bytes from the buffer
        else:
            result = self.buffer[:n]
            del self.buffer[:n]

        return result

    def feed_eof(self) -> None:
        pass

class WebSocketResponseWriter(WriterAdapter):
    """Interface to allow mqtt broker to write to an aiohttp websocket connection."""

    def __init__(self, ws: web.WebSocketResponse, request: web.Request):
        super().__init__()
        self.ws = ws

        # needed for `get_peer_info`
        # https://docs.python.org/3/library/socket.html#socket.socket.getpeername
        peer_name = request.transport.get_extra_info('peername')
        if peer_name is not None:
            self.client_ip, self.port = peer_name[0:2]
        else:
            self.client_ip, self.port = request.remote, 0

        # interpret AF_INET6
        self.client_ip = "localhost" if self.client_ip == "::1" else self.client_ip

        self._stream = io.BytesIO(b"")

    def write(self, data: bytes) -> None:
        """Add bytes to stream buffer."""
        self._stream.write(data)

    async def drain(self) -> None:
        """Send the collected bytes in the buffer to the websocket connection."""
        data = self._stream.getvalue()
        if data and len(data):
            await self.ws.send_bytes(data)
        self._stream = io.BytesIO(b"")

    def get_peer_info(self) -> tuple[str, int] | None:
        return self.client_ip, self.port

    async def close(self) -> None:
        # no clean up needed, stream will be gc along with instance
        pass

async def mqtt_websocket_handler(request: web.Request) -> web.StreamResponse:

    # establish connection by responding to the websocket request with the 'mqtt' protocol
    ws = web.WebSocketResponse(protocols=['mqtt',])
    await ws.prepare(request)

    # access the broker created when the server started
    b: Broker = request.app['broker']

    # hand-off the websocket data stream to the broker for handling
    # `listener_name` is the same name of the externalized listener in the broker config
    await b.external_connected(WebSocketResponseReader(ws), WebSocketResponseWriter(ws, request), MQTT_LISTENER_NAME)

    logger.debug('websocket connection closed')
    return ws


async def websocket_handler(request: web.Request) -> web.StreamResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        logging.info(msg)

    logging.info("websocket connection closed")
    return ws

def main():
    # create an `aiohttp` server
    lp = asyncio.get_event_loop()
    app = web.Application()
    app.add_routes(
        [
            web.get('/', hello), # http get request/response route
            web.get('/ws', websocket_handler), # standard websocket handler
            web.get('/mqtt', mqtt_websocket_handler), # websocket handler for mqtt connections
        ])
    # create background task for running the `amqtt` broker
    app.cleanup_ctx.append(run_broker)

    # make sure that both `aiohttp` server and `amqtt` broker run in the same loop
    #  so the server can hand off the connection to the broker (prevents attached-to-a-different-loop `RuntimeError`)
    web.run_app(app, loop=lp)


async def run_broker(_app):
    """App init function to start (and then shutdown) the `amqtt` broker.
    https://docs.aiohttp.org/en/stable/web_advanced.html#background-tasks"""

    # standard TCP connection as well as an externalized-listener
    cfg = BrokerConfig(
        listeners={
            'default':ListenerConfig(type=ListenerType.TCP, bind='127.0.0.1:1883'),
            MQTT_LISTENER_NAME: ListenerConfig(type=ListenerType.EXTERNAL),
        }
    )

    # make sure the `Broker` runs in the same loop as the aiohttp server
    loop = asyncio.get_event_loop()
    broker = Broker(config=cfg, loop=loop)

    # store broker instance so that incoming requests can hand off processing of a datastream
    _app['broker'] = broker
    # start the broker
    await broker.start()

    # pass control back to web app
    yield

    # closing activities
    await broker.shutdown()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
