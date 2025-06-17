import asyncio
import unittest

import pytest

from amqtt.adapters import BufferReader
from amqtt.errors import MQTTError
from amqtt.mqtt.packet import CONNECT, MQTTFixedHeader


class TestMQTTFixedHeaderTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_bytes(self):
        data = b"\x10\x7f"
        stream = BufferReader(data)
        header = self.loop.run_until_complete(MQTTFixedHeader.from_stream(stream))
        assert header.packet_type == CONNECT
        assert not header.flags & 8
        assert (header.flags & 6) >> 1 == 0
        assert not header.flags & 1
        assert header.remaining_length == 127

    def test_from_bytes_with_length(self):
        data = b"\x10\xff\xff\xff\x7f"
        stream = BufferReader(data)
        header = self.loop.run_until_complete(MQTTFixedHeader.from_stream(stream))
        assert header.packet_type == CONNECT
        assert not header.flags & 8
        assert (header.flags & 6) >> 1 == 0
        assert not header.flags & 1
        assert header.remaining_length == 268435455

    def test_from_bytes_ko_with_length(self):
        data = b"\x10\xff\xff\xff\xff\x7f"
        stream = BufferReader(data)
        with pytest.raises(MQTTError):
            self.loop.run_until_complete(MQTTFixedHeader.from_stream(stream))

    def test_to_bytes(self):
        header = MQTTFixedHeader(CONNECT, 0x00, 0)
        data = header.to_bytes()
        assert data == b"\x10\x00"

    def test_to_bytes_2(self):
        header = MQTTFixedHeader(CONNECT, 0x00, 268435455)
        data = header.to_bytes()
        assert data == b"\x10\xff\xff\xff\x7f"
