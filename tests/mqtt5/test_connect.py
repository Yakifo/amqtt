import asyncio

from hypothesis import given, strategies as st
import pytest

from amqtt.adapters import BufferReader
from amqtt.errors import AMQTTError, MQTTError
from amqtt.mqtt3.connect import ConnectPacket as ConnectV3Packet
from amqtt.mqtt3.packet import MQTTFixedHeader, PUBLISH
from amqtt.mqtt5.connect import ConnectPacket
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    CONTENT_TYPE,
    PACKET_CONNECT,
    PACKET_WILL,
    RECEIVE_MAXIMUM,
    REQUEST_PROBLEM_INFORMATION,
    SESSION_EXPIRY_INTERVAL,
    USER_PROPERTY,
    WILL_DELAY_INTERVAL,
)


def test_decode_spec_example_minimal_clean_start() -> None:
    data = b"\x10\x13\x00\x04MQTT\x05\x02\x00\x00\x00\x00\x06client"

    packet = asyncio.run(ConnectPacket.from_stream(BufferReader(data)))

    assert packet.proto_name == "MQTT"
    assert packet.proto_level == 5
    assert packet.clean_start_flag is True
    assert packet.keep_alive == 0
    assert packet.properties == Properties(packet_name=PACKET_CONNECT)
    assert packet.client_id == "client"
    assert packet.will_flag is False
    assert packet.username is None
    assert packet.password is None
    assert packet.to_bytes() == data


def test_connect_round_trip_with_connect_and_will_properties() -> None:
    properties = Properties(packet_name=PACKET_CONNECT)
    properties.set(SESSION_EXPIRY_INTERVAL, 300)
    properties.set(RECEIVE_MAXIMUM, 10)
    properties.set(REQUEST_PROBLEM_INFORMATION, 0)
    properties.set(USER_PROPERTY, ("source", "test"))
    will_properties = Properties(packet_name=PACKET_WILL)
    will_properties.set(WILL_DELAY_INTERVAL, 5)
    will_properties.set(CONTENT_TYPE, "text/plain")
    will_properties.set(USER_PROPERTY, ("wk", "wv"))
    expected = (
        b"\x10\x6e\x00\x04MQTT\x05\xee\x00\x3c"
        b"\x19\x11\x00\x00\x01\x2c\x21\x00\x0a\x17\x00\x26\x00\x06source\x00\x04test"
        b"\x00\x08client-1"
        b"\x1b\x18\x00\x00\x00\x05\x03\x00\x0atext/plain\x26\x00\x02wk\x00\x02wv"
        b"\x00\x0awill/topic\x00\x07offline\x00\x04user\x00\x07\x00secret"
    )

    packet = ConnectPacket.build(
        "client-1",
        clean_start=True,
        keep_alive=60,
        properties=properties,
        will_topic="will/topic",
        will_message=b"offline",
        will_qos=1,
        will_retain=True,
        will_properties=will_properties,
        username="user",
        password=b"\x00secret",
    )
    decoded = asyncio.run(ConnectPacket.from_stream(BufferReader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.to_bytes() == expected
    assert decoded.properties == properties
    assert decoded.will_properties == will_properties
    assert decoded.will_qos == 1
    assert decoded.will_retain_flag is True
    assert decoded.username == "user"
    assert decoded.password == b"\x00secret"


def test_password_can_be_binary_without_username() -> None:
    data = b"\x10\x17\x00\x04MQTT\x05\x40\x00\x00\x00\x00\x06client\x00\x02\xff\x00"

    packet = asyncio.run(ConnectPacket.from_stream(BufferReader(data)))

    assert packet.username_flag is False
    assert packet.password_flag is True
    assert packet.username is None
    assert packet.password == b"\xff\x00"
    assert packet.to_bytes() == data


def test_mqtt3_connect_parsing_is_unchanged() -> None:
    data = (
        b"\x10\x3e\x00\x04MQTT\x04\xce\x00\x00\x00\x0a0123456789"
        b"\x00\x09WillTopic\x00\x0bWillMessage\x00\x04user\x00\x08password"
    )

    packet = asyncio.run(ConnectV3Packet.from_stream(BufferReader(data)))

    assert packet.proto_level == 4
    assert packet.password == "password"
    assert packet.to_bytes() == data


def test_incorrect_fixed_header() -> None:
    header = MQTTFixedHeader(PUBLISH, 0x00)

    with pytest.raises(AMQTTError):
        ConnectPacket(fixed=header)


@pytest.mark.parametrize(
    "data",
    [
        b"\x11\x13\x00\x04MQTT\x05\x02\x00\x00\x00\x00\x06client",
        b"\x10\x13\x00\x04MQTT\x05\x03\x00\x00\x00\x00\x06client",
        b"\x10\x13\x00\x04MQTT\x04\x02\x00\x00\x00\x00\x06client",
        b"\x10\x13\x00\x04MQTT\x05\x06\x00\x00\x00\x00\x06client",
        b"\x10\x19\x00\x04MQTT\x05\x02\x00\x00\x00\x00\x06client\x00\x04user",
        b"\x10\x1d\x00\x04MQTT\x05\x02\x00\x00\x0a\x11\x00\x00\x00\x01\x11\x00\x00\x00\x02\x00\x06client",
    ],
)
def test_malformed_connect_input_raises(data: bytes) -> None:
    with pytest.raises(MQTTError):
        asyncio.run(ConnectPacket.from_stream(BufferReader(data)))


def test_build_rejects_non_connect_properties() -> None:
    properties = Properties()
    properties.set(CONTENT_TYPE, "text/plain")

    with pytest.raises(MQTTError):
        ConnectPacket.build("client", properties=properties)


def test_build_rejects_incomplete_will() -> None:
    with pytest.raises(MQTTError):
        ConnectPacket.build("client", will_properties=Properties(packet_name=PACKET_WILL))


@given(st.binary())
def test_connect_decode_never_crashes(data: bytes) -> None:
    try:
        asyncio.run(ConnectPacket.from_stream(BufferReader(data)))
    except (AMQTTError, MQTTError):
        pass

