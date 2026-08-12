import asyncio
import unittest

from amqtt.adapters import BufferReader
from amqtt.mqtt3.constants import QOS_1, QOS_2
from amqtt.mqtt3.packet import PacketIdVariableHeader
from amqtt.mqtt3.subscribe import SubscribePacket, SubscribePayload


class SubscribePacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_stream(self):
        data = b"\x80\x0e\x00\x0a\x00\x03a/b\x01\x00\x03c/d\x02"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(SubscribePacket.from_stream(stream))
        (topic, qos) = message.payload.topics[0]
        assert topic == "a/b"
        assert qos == QOS_1
        (topic, qos) = message.payload.topics[1]
        assert topic == "c/d"
        assert qos == QOS_2

    def test_to_stream(self):
        variable_header = PacketIdVariableHeader(10)
        payload = SubscribePayload([("a/b", QOS_1), ("c/d", QOS_2)])
        publish = SubscribePacket(variable_header=variable_header, payload=payload)
        out = publish.to_bytes()
        assert out == b"\x82\x0e\x00\n\x00\x03a/b\x01\x00\x03c/d\x02"
