import asyncio
import unittest

from amqtt.adapters import BufferReader
from amqtt.mqtt.pubrel import PacketIdVariableHeader, PubrelPacket


class PubrelPacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_stream(self):
        data = b"\x60\x02\x00\x0a"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(PubrelPacket.from_stream(stream))
        assert message.variable_header.packet_id == 10

    def test_to_bytes(self):
        variable_header = PacketIdVariableHeader(10)
        publish = PubrelPacket(variable_header=variable_header)
        out = publish.to_bytes()
        assert out == b"b\x02\x00\n"
