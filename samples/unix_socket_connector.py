import asyncio
import contextlib
import logging
from asyncio import StreamWriter, StreamReader, Event

from amqtt.adapters import ReaderAdapter, WriterAdapter


logger = logging.getLogger(__name__)


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
        if not self.is_closed:
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
