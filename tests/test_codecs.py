import asyncio
import unittest

import pytest

from amqtt.adapters import BufferReader, StreamReaderAdapter
from amqtt.errors import MQTTError
from amqtt.codecs_amqtt import (
    bytes_to_hex_str,
    bytes_to_int,
    decode_variable_byte_int,
    decode_string,
    encode_variable_byte_int,
    encode_string,
    int_to_bytes,
    read_exact,
    require_exact,
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

    def test_int_to_bytes_supports_four_byte_values(self):
        assert int_to_bytes(0xFFFF_FFFF, 4) == b"\xff\xff\xff\xff"

    def test_variable_byte_integer_round_trip(self):
        for value, encoded in [
            (0, b"\x00"),
            (127, b"\x7f"),
            (128, b"\x80\x01"),
            (16_383, b"\xff\x7f"),
            (16_384, b"\x80\x80\x01"),
            (268_435_455, b"\xff\xff\xff\x7f"),
        ]:
            assert encode_variable_byte_int(value) == encoded
            assert decode_variable_byte_int(encoded) == (value, len(encoded))

    def test_decode_string(self):
        stream = asyncio.StreamReader(loop=self.loop)
        stream.feed_data(b"\x00\x02AA")
        ret = self.loop.run_until_complete(decode_string(StreamReaderAdapter(stream)))
        assert ret == "AA"

    def test_read_exact(self):
        stream = BufferReader(b"AA")
        ret = self.loop.run_until_complete(read_exact(stream, 2, "test field"))
        assert ret == b"AA"

    def test_read_exact_raises_for_short_read(self):
        stream = BufferReader(b"A")
        with pytest.raises(MQTTError, match="test field is shorter than expected"):
            self.loop.run_until_complete(read_exact(stream, 2, "test field"))

    def test_require_exact(self):
        require_exact(1, 3, 2, "test field")

    def test_require_exact_raises_for_short_buffer(self):
        with pytest.raises(MQTTError, match="test field is shorter than expected"):
            require_exact(1, 2, 2, "test field")

    def test_encode_string(self):
        encoded = encode_string("AA")
        assert encoded == b"\x00\x02AA"
