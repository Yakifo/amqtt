# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import asyncio
import unittest

from amqtt.adapters import BufferReader
from amqtt.mqtt.connect import ConnectPacket, ConnectPayload, ConnectVariableHeader
from amqtt.mqtt.packet import CONNECT, MQTTFixedHeader


class ConnectPacketTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_decode_ok(self):
        data = b"\x10\x3e\x00\x04MQTT\x04\xce\x00\x00\x00\x0a0123456789\x00\x09WillTopic\x00\x0bWillMessage\x00\x04user\x00\x08password"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.variable_header.proto_name == "MQTT"
        assert message.variable_header.proto_level == 4
        assert message.variable_header.username_flag
        assert message.variable_header.password_flag
        assert not message.variable_header.will_retain_flag
        assert message.variable_header.will_qos == 1
        assert message.variable_header.will_flag
        assert message.variable_header.clean_session_flag
        assert not message.variable_header.reserved_flag
        assert message.payload.client_id == "0123456789"
        assert message.payload.will_topic == "WillTopic"
        assert message.payload.will_message == b"WillMessage"
        assert message.payload.username == "user"
        assert message.payload.password == "password"

    def test_decode_ok_will_flag(self):
        data = b"\x10\x26\x00\x04MQTT\x04\xca\x00\x00\x00\x0a0123456789\x00\x04user\x00\x08password"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.variable_header.proto_name == "MQTT"
        assert message.variable_header.proto_level == 4
        assert message.variable_header.username_flag
        assert message.variable_header.password_flag
        assert not message.variable_header.will_retain_flag
        assert message.variable_header.will_qos == 1
        assert not message.variable_header.will_flag
        assert message.variable_header.clean_session_flag
        assert not message.variable_header.reserved_flag
        assert message.payload.client_id == "0123456789"
        assert message.payload.will_topic is None
        assert message.payload.will_message is None
        assert message.payload.username == "user"
        assert message.payload.password == "password"

    def test_decode_fail_reserved_flag(self):
        data = b"\x10\x3e\x00\x04MQTT\x04\xcf\x00\x00\x00\x0a0123456789\x00\x09WillTopic\x00\x0bWillMessage\x00\x04user\x00\x08password"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.variable_header.reserved_flag

    def test_decode_fail_miss_clientId(self):
        data = b"\x10\x0a\x00\x04MQTT\x04\xce\x00\x00"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.payload.client_id is not None

    def test_decode_fail_miss_willtopic(self):
        data = b"\x10\x16\x00\x04MQTT\x04\xce\x00\x00\x00\x0a0123456789"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.payload.will_topic is None

    def test_decode_fail_miss_username(self):
        data = b"\x10\x2e\x00\x04MQTT\x04\xce\x00\x00\x00\x0a0123456789\x00\x09WillTopic\x00\x0bWillMessage"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.payload.username is None

    def test_decode_fail_miss_password(self):
        data = b"\x10\x34\x00\x04MQTT\x04\xce\x00\x00\x00\x0a0123456789\x00\x09WillTopic\x00\x0bWillMessage\x00\x04user"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.payload.password is None

    def test_encode(self):
        header = MQTTFixedHeader(CONNECT, 0x00, 0)
        variable_header = ConnectVariableHeader(0xCE, 0, "MQTT", 4)
        payload = ConnectPayload(
            "0123456789",
            "WillTopic",
            b"WillMessage",
            "user",
            "password",
        )
        message = ConnectPacket(header, variable_header, payload)
        encoded = message.to_bytes()
        assert (
            encoded
            == b"\x10>\x00\x04MQTT\x04\xce\x00\x00\x00\n0123456789\x00\tWillTopic\x00\x0bWillMessage\x00\x04user\x00\x08password"
        )

    def test_getattr_ok(self):
        data = b"\x10\x3e\x00\x04MQTT\x04\xce\x00\x00\x00\x0a0123456789\x00\x09WillTopic\x00\x0bWillMessage\x00\x04user\x00\x08password"
        stream = BufferReader(data)
        message = self.loop.run_until_complete(ConnectPacket.from_stream(stream))
        assert message.variable_header.proto_name == "MQTT"
        assert message.proto_name == "MQTT"
        assert message.variable_header.proto_level == 4
        assert message.proto_level == 4
        assert message.variable_header.username_flag
        assert message.username_flag
        assert message.variable_header.password_flag
        assert message.password_flag
        assert not message.variable_header.will_retain_flag
        assert not message.will_retain_flag
        assert message.variable_header.will_qos == 1
        assert message.will_qos == 1
        assert message.variable_header.will_flag
        assert message.will_flag
        assert message.variable_header.clean_session_flag
        assert message.clean_session_flag
        assert not message.variable_header.reserved_flag
        assert not message.reserved_flag
        assert message.payload.client_id == "0123456789"
        assert message.client_id == "0123456789"
        assert message.payload.will_topic == "WillTopic"
        assert message.will_topic == "WillTopic"
        assert message.payload.will_message == b"WillMessage"
        assert message.will_message == b"WillMessage"
        assert message.payload.username == "user"
        assert message.username == "user"
        assert message.payload.password == "password"
        assert message.password == "password"
