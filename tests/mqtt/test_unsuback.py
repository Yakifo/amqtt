import asyncio
import unittest

from amqtt.adapters import BufferReader
from amqtt.mqtt.packet import PacketIdVariableHeader
from amqtt.mqtt.unsuback import UnsubackPacket


class UnsubackPacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_stream(self):
        data = b"\xb0\x02\x00\x0a"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(UnsubackPacket.from_stream(stream))
        assert message.variable_header is not None
        assert message.variable_header.packet_id == 10

    def test_to_stream(self):
        variable_header = PacketIdVariableHeader(10)
        publish = UnsubackPacket(variable_header=variable_header)
        out = publish.to_bytes()
        assert out == b"\xb0\x02\x00\n"
