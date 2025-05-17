import asyncio
import unittest

from amqtt.adapters import BufferReader
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.mqtt.publish import PublishPacket, PublishPayload, PublishVariableHeader


class PublishPacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_stream_qos_0(self):
        data = b"\x31\x11\x00\x05topic0123456789"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(PublishPacket.from_stream(stream))
        assert message.variable_header.topic_name == "topic"
        assert message.variable_header.packet_id is None
        assert not message.fixed_header.flags >> 1 & 3
        assert message.fixed_header.flags & 0x01
        assert message.payload.data, b"0123456789"

    def test_from_stream_qos_2(self):
        data = b"\x37\x13\x00\x05topic\x00\x0a0123456789"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(PublishPacket.from_stream(stream))
        assert message.variable_header.topic_name == "topic"
        assert message.variable_header.packet_id == 10
        assert (message.fixed_header.flags >> 1) & 0x03
        assert message.fixed_header.flags & 0x01
        assert message.payload.data, b"0123456789"

    def test_to_stream_no_packet_id(self):
        variable_header = PublishVariableHeader("topic", None)
        payload = PublishPayload(b"0123456789")
        publish = PublishPacket(variable_header=variable_header, payload=payload)
        out = publish.to_bytes()
        assert out == b"0\x11\x00\x05topic0123456789"

    def test_to_stream_packet(self):
        variable_header = PublishVariableHeader("topic", 10)
        payload = PublishPayload(b"0123456789")
        publish = PublishPacket(variable_header=variable_header, payload=payload)
        out = publish.to_bytes()
        assert out == b"0\x13\x00\x05topic\x00\n0123456789"

    def test_build(self):
        packet = PublishPacket.build("/topic", b"data", 1, False, QOS_0, False)
        assert packet.packet_id == 1
        assert not packet.dup_flag
        assert packet.qos == QOS_0
        assert not packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, False, QOS_1, False)
        assert packet.packet_id == 1
        assert not packet.dup_flag
        assert packet.qos == QOS_1
        assert not packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, False, QOS_2, False)
        assert packet.packet_id == 1
        assert not packet.dup_flag
        assert packet.qos == QOS_2
        assert not packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, True, QOS_0, False)
        assert packet.packet_id == 1
        assert packet.dup_flag
        assert packet.qos == QOS_0
        assert not packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, True, QOS_1, False)
        assert packet.packet_id == 1
        assert packet.dup_flag
        assert packet.qos == QOS_1
        assert not packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, True, QOS_2, False)
        assert packet.packet_id == 1
        assert packet.dup_flag
        assert packet.qos == QOS_2
        assert not packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, False, QOS_0, True)
        assert packet.packet_id == 1
        assert not packet.dup_flag
        assert packet.qos == QOS_0
        assert packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, False, QOS_1, True)
        assert packet.packet_id == 1
        assert not packet.dup_flag
        assert packet.qos == QOS_1
        assert packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, False, QOS_2, True)
        assert packet.packet_id == 1
        assert not packet.dup_flag
        assert packet.qos == QOS_2
        assert packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, True, QOS_0, True)
        assert packet.packet_id == 1
        assert packet.dup_flag
        assert packet.qos == QOS_0
        assert packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, True, QOS_1, True)
        assert packet.packet_id == 1
        assert packet.dup_flag
        assert packet.qos == QOS_1
        assert packet.retain_flag

        packet = PublishPacket.build("/topic", b"data", 1, True, QOS_2, True)
        assert packet.packet_id == 1
        assert packet.dup_flag
        assert packet.qos == QOS_2
        assert packet.retain_flag
