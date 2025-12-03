import asyncio
import unittest
import pytest

from amqtt.adapters import BufferReader
from amqtt.errors import AMQTTError
from amqtt.mqtt3 import MQTTFixedHeader, PUBLISH
from amqtt.mqtt3.pubcomp import PacketIdVariableHeader, PubcompPacket


class PubcompPacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_stream(self):
        data = b"\x70\x02\x00\x0a"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(PubcompPacket.from_stream(stream))
        assert message.variable_header.packet_id == 10

    def test_to_bytes(self):
        variable_header = PacketIdVariableHeader(10)
        publish = PubcompPacket(variable_header=variable_header)
        out = publish.to_bytes()
        assert out == b"p\x02\x00\n"

def test_incorrect_fixed_header():
    header = MQTTFixedHeader(PUBLISH, 0x00)
    with pytest.raises(AMQTTError):
        _ = PubcompPacket(fixed=header)


@pytest.mark.parametrize("prop", [
    "packet_id"
])
def test_empty_variable_header(prop):
    packet = PubcompPacket()

    with pytest.raises(ValueError):
        assert getattr(packet, prop) is not None

    with pytest.raises(ValueError):
        assert setattr(packet, prop, "a value")
