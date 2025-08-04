import asyncio
import logging

import aiohttp
from aiohttp import web

from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig, ListenerConfig, ListenerType
from amqtt.errors import BrokerError


async def hello(request):
    return web.Response(text="Hello, world")



class AIOWebSocketsReader(ReaderAdapter):
    def __init__(self, ws: web.WebSocketResponse):
        self.ws = ws
        self.buffer = bytearray()
        self.closed = False

    async def read(self, n: int = -1) -> bytes:
        print(f"attempting to read {n} bytes")
        while not self.buffer and not self.closed or len(self.buffer) < n:
            msg = await self.ws.receive()
            if msg.type == aiohttp.WSMsgType.BINARY:
                self.buffer.extend(msg.data)
            elif msg.type == aiohttp.WSMsgType.CLOSE:
                self.closed = True
        print(f"buffer size: {len(self.buffer)}")
        if n == -1:
            result = bytes(self.buffer)
            self.buffer.clear()
        else:
            result = self.buffer[:n]
            del self.buffer[:n]
        print(f"bytes: {result}")
        return result

    def feed_eof(self) -> None:
        pass

class AIOWebSocketsWriter(WriterAdapter):

    def __init__(self, ws: web.WebSocketResponse):
        super().__init__()
        self.ws = ws

    def write(self, data: bytes) -> None:
        print(f"broker wants to write data: {data}")
        self.ws.send_bytes(data)


    async def drain(self) -> None:
        pass

    def get_peer_info(self) -> tuple[str, int] | None:
        return "aiohttp", 1234567

    async def close(self) -> None:
        pass


async def websocket_handler(request):
    print()
    ws = web.WebSocketResponse(protocols=['mqtt',])
    await ws.prepare(request)
    #
    # readQ = asyncio.Queue()
    # writeQ = asyncio.Queue()
    #
    # async def receiver():
    #     async for msg in ws:
    #         match msg.type:
    #             case aiohttp.WSMsgType.BINARY:
    #                 readQ.put_nowait(msg.data)
    #             case _:
    #                 return
    #
    # async def send_items():
    #     while not ws.closed:
    #         if not writeQ.empty():
    #             item = await writeQ.get()
    #             await ws.send_bytes(item)
    #
    # await asyncio.create_task(send_items())
    #
    b: Broker = request.app['broker']
    await b._client_connected('aiohttp', AIOWebSocketsReader(ws), AIOWebSocketsWriter(ws))

    # async for msg in ws:
    #     print(f"ws: {msg}")



        #
        # elif msg.type == aiohttp.WSMsgType.ERROR:
        #     print('ws connection closed with exception %s' %
        #           ws.exception())

    print('websocket connection closed')

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
    loop = asyncio.get_event_loop()

    cfg = BrokerConfig(
        listeners={
            'default':ListenerConfig(type=ListenerType.WS, bind='127.0.0.1:8883'),
            'aiohttp': ListenerConfig(type=ListenerType.AIOHTTP),
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
