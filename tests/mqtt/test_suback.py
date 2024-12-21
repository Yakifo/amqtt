# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import asyncio
import unittest

from amqtt.adapters import BufferReader
from amqtt.mqtt.packet import PacketIdVariableHeader
from amqtt.mqtt.suback import SubackPacket, SubackPayload


class SubackPacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_from_stream(self):
        data = b"\x90\x06\x00\x0a\x00\x01\x02\x80"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(SubackPacket.from_stream(stream))
        assert message.payload.return_codes[0] == SubackPayload.RETURN_CODE_00
        assert message.payload.return_codes[1] == SubackPayload.RETURN_CODE_01
        assert message.payload.return_codes[2] == SubackPayload.RETURN_CODE_02
        assert message.payload.return_codes[3] == SubackPayload.RETURN_CODE_80

    def test_to_stream(self):
        variable_header = PacketIdVariableHeader(10)
        payload = SubackPayload(
            [
                SubackPayload.RETURN_CODE_00,
                SubackPayload.RETURN_CODE_01,
                SubackPayload.RETURN_CODE_02,
                SubackPayload.RETURN_CODE_80,
            ],
        )
        suback = SubackPacket(variable_header=variable_header, payload=payload)
        out = suback.to_bytes()
        assert out == b"\x90\x06\x00\n\x00\x01\x02\x80"
