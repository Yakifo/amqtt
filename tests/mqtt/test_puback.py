import asyncio
import unittest

from amqtt.adapters import BufferReader
from amqtt.mqtt.puback import PacketIdVariableHeader, PubackPacket


class PubackPacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_stream(self):
        data = b"\x40\x02\x00\x0a"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(PubackPacket.from_stream(stream))
        assert message.variable_header.packet_id == 10

    def test_to_bytes(self):
        variable_header = PacketIdVariableHeader(10)
        publish = PubackPacket(variable_header=variable_header)
        out = publish.to_bytes()
        assert out == b"@\x02\x00\n"
