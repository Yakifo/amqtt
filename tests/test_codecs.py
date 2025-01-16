import asyncio
import unittest

from amqtt.adapters import StreamReaderAdapter
from amqtt.codecs_amqtt import (
    bytes_to_hex_str,
    bytes_to_int,
    decode_string,
    encode_string,
)


class TestCodecs(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_bytes_to_hex_str(self):
        ret = bytes_to_hex_str(b"\x7f")
        assert ret == "0x7f"

    def test_bytes_to_int(self):
        ret = bytes_to_int(b"\x7f")
        assert ret == 127
        ret = bytes_to_int(b"\xff\xff")
        assert ret == 65535

    def test_decode_string(self):
        stream = asyncio.StreamReader(loop=self.loop)
        stream.feed_data(b"\x00\x02AA")
        ret = self.loop.run_until_complete(decode_string(StreamReaderAdapter(stream)))
        assert ret == "AA"

    def test_encode_string(self):
        encoded = encode_string("AA")
        assert encoded == b"\x00\x02AA"
