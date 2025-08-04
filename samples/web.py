import asyncio
import io
import logging

import aiohttp
from aiohttp import web

from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig, ListenerConfig, ListenerType


logger = logging.getLogger(__name__)


async def hello(request):
    return web.Response(text="Hello, world")

class WebSocketResponseReader(ReaderAdapter):
    """Interface to allow mqtt broker to read from an aiohttp websocket connection."""

    def __init__(self, ws: web.WebSocketResponse):
        self.ws = ws
        self.buffer = bytearray()

    async def read(self, n: int = -1) -> bytes:
        """
        Raises:
            BrokerPipeError : if reading on a closed websocket connection
        """
        # continue until buffer contains at least the amount of data being requested
        while not self.buffer or len(self.buffer) < n:
            if self.ws.closed:
                raise BrokenPipeError()
            try:
                async with asyncio.timeout(0.5):
                    msg = await self.ws.receive()
                    if msg.type == aiohttp.WSMsgType.BINARY:
                        self.buffer.extend(msg.data)
                    elif msg.type == aiohttp.WSMsgType.CLOSE:
                        raise BrokenPipeError()
            except asyncio.TimeoutError:
                raise BrokenPipeError()

        if n == -1:
            result = bytes(self.buffer)
            self.buffer.clear()
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
        self._stream.write(data)

    async def drain(self) -> None:
        data = self._stream.getvalue()
        if data and len(data):
            await self.ws.send_bytes(data)
        self._stream = io.BytesIO(b"")

    def get_peer_info(self) -> tuple[str, int] | None:
        return self.client_ip, self.port

    async def close(self) -> None:
        pass


async def websocket_handler(request: web.Request) -> web.StreamResponse:

    # respond to the websocket request with the 'mqtt' protocol
    ws = web.WebSocketResponse(protocols=['mqtt',])
    await ws.prepare(request)

    # access the broker created when the server started and notify the broker of this new connection
    b: Broker = request.app['broker']

    # send/receive data to the websocket. must pass the name of the externalized listener in the broker config
    await b.external_connected(WebSocketResponseReader(ws), WebSocketResponseWriter(ws, request), 'myAIOHttp')

    logger.debug('websocket connection closed')
    return ws


def main():

    app = web.Application()
    app.add_routes(
        [
            web.get('/', hello),
            web.get('/ws', websocket_handler)
        ])
    app.cleanup_ctx.append(run_broker)
    web.run_app(app)


async def run_broker(_app):
    """https://docs.aiohttp.org/en/stable/web_advanced.html#background-tasks"""
    loop = asyncio.get_event_loop()

    cfg = BrokerConfig(
        listeners={
            'default':ListenerConfig(type=ListenerType.TCP, bind='127.0.0.1:1883'),
            'myAIOHttp': ListenerConfig(type=ListenerType.EXTERNAL),
        }
    )

    broker = Broker(config=cfg, loop=loop)
    _app['broker'] = broker
    await broker.start()

    yield

    await broker.shutdown()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
