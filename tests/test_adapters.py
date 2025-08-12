import ssl

import pytest

from amqtt.adapters import ReaderAdapter, WriterAdapter


class BrokenReaderAdapter(ReaderAdapter):

    async def read(self, n: int = -1) -> bytes:
        return await super().read(n)

    def feed_eof(self) -> None:
        return super().feed_eof()


@pytest.mark.asyncio
async def test_abstract_read_raises():
    reader = BrokenReaderAdapter()
    with pytest.raises(NotImplementedError):
        await reader.read()

    with pytest.raises(NotImplementedError):
        reader.feed_eof()

class BrokerWriterAdapter(WriterAdapter):
    def write(self, data: bytes) -> None:
        super().write(data)

    async def drain(self) -> None:
        await super().drain()

    def get_peer_info(self) -> tuple[str, int] | None:
        return super().get_peer_info()

    def get_ssl_info(self) -> ssl.SSLObject | None:
        return None

    async def close(self) -> None:
        await super().close()

@pytest.mark.asyncio
async def test_abstract_write_raises():
    writer = BrokerWriterAdapter()
    with pytest.raises(NotImplementedError):
        writer.write(b'')

    with pytest.raises(NotImplementedError):
        await writer.drain()

    with pytest.raises(NotImplementedError):
        writer.get_peer_info()

    with pytest.raises(NotImplementedError):
        await writer.close()
