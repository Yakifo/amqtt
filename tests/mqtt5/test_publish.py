import asyncio

from hypothesis import given, strategies as st
import pytest

from amqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.errors import AMQTTError, MQTTError
from amqtt.mqtt3.packet import CONNECT, MQTTFixedHeader
from amqtt.mqtt3.publish import PublishPacket as PublishV3Packet
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    CONTENT_TYPE,
    MESSAGE_EXPIRY_INTERVAL,
    PACKET_CONNECT,
    PACKET_PUBLISH,
    PAYLOAD_FORMAT_INDICATOR,
    RESPONSE_TOPIC,
    SESSION_EXPIRY_INTERVAL,
    TOPIC_ALIAS,
    USER_PROPERTY,
)
from amqtt.mqtt5.publish import PublishPacket, PublishPayload, PublishVariableHeader


def test_decode_spec_example_publish_variable_header_no_properties(make_reader) -> None:
    data = b"\x32\x08\x00\x03a/b\x00\x0a\x00"

    packet = asyncio.run(PublishPacket.from_stream(make_reader(data)))

    assert packet.topic_name == "a/b"
    assert packet.packet_id == 10
    assert packet.qos == QOS_1
    assert packet.properties == Properties(packet_name=PACKET_PUBLISH)
    assert packet.data == b""
    assert packet.to_bytes() == data


def test_publish_round_trip_with_properties(make_reader) -> None:
    properties = Properties(packet_name=PACKET_PUBLISH)
    properties.set(PAYLOAD_FORMAT_INDICATOR, 1)
    properties.set(MESSAGE_EXPIRY_INTERVAL, 60)
    properties.set(RESPONSE_TOPIC, "reply/to")
    properties.set(CONTENT_TYPE, "application/json")
    properties.set(USER_PROPERTY, ("source", "test"))
    properties.set(USER_PROPERTY, ("source", "again"))
    expected = (
        b"\x33\x5d\x00\x0csensors/temp\x00\x07"
        b"\x44\x01\x01\x02\x00\x00\x00\x3c\x08\x00\x08reply/to"
        b"\x03\x00\x10application/json"
        b"\x26\x00\x06source\x00\x04test"
        b"\x26\x00\x06source\x00\x05again"
        b'{"t":20}'
    )

    packet = PublishPacket.build("sensors/temp", b'{"t":20}', 7, False, QOS_1, True, properties)
    decoded = asyncio.run(PublishPacket.from_stream(make_reader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.to_bytes() == expected
    assert decoded.topic_name == "sensors/temp"
    assert decoded.packet_id == 7
    assert decoded.qos == QOS_1
    assert decoded.retain_flag is True
    assert decoded.data == b'{"t":20}'
    assert decoded.properties == properties
    assert decoded.properties.get(USER_PROPERTY) == [("source", "test"), ("source", "again")]


def test_zero_length_topic_with_topic_alias_encodes_correctly(make_reader) -> None:
    properties = Properties(packet_name=PACKET_PUBLISH)
    properties.set(TOPIC_ALIAS, 2)
    expected = b"\x30\x0a\x00\x00\x03\x23\x00\x02data"

    packet = PublishPacket.build("", b"data", None, False, QOS_0, False, properties)
    decoded = asyncio.run(PublishPacket.from_stream(make_reader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.to_bytes() == expected
    assert decoded.topic_name == ""
    assert decoded.properties.get(TOPIC_ALIAS) == 2
    assert decoded.data == b"data"


def test_mqtt3_publish_parsing_is_unchanged(make_reader) -> None:
    data = b"\x31\x11\x00\x05topic0123456789"

    packet = asyncio.run(PublishV3Packet.from_stream(make_reader(data)))

    assert packet.topic_name == "topic"
    assert packet.packet_id is None
    assert packet.data == b"0123456789"
    assert packet.to_bytes() == data


def test_incorrect_fixed_header() -> None:
    header = MQTTFixedHeader(CONNECT, 0x00)

    with pytest.raises(AMQTTError):
        PublishPacket(fixed=header)


@pytest.mark.parametrize(
    "data",
    [
        b"\x36\x00",
        b"\x38\x03\x00\x01a\x00",
        b"\x30\x03\x00\x00\x00",
        b"\x32\x06\x00\x01a\x00\x00\x00",
        b"\x30\x05\x00\x01#\x00x",
        b"\x30\x0d\x00\x01a\x09\x03\x00\x04text\x03\x00\x04json",
    ],
)
def test_malformed_publish_input_raises(data: bytes, make_reader) -> None:
    with pytest.raises(MQTTError):
        asyncio.run(PublishPacket.from_stream(make_reader(data)))


def test_build_rejects_non_publish_properties() -> None:
    properties = Properties(packet_name=PACKET_CONNECT)
    properties.set(SESSION_EXPIRY_INTERVAL, 60)

    with pytest.raises(MQTTError):
        PublishPacket.build("topic", b"data", None, False, QOS_0, False, properties)


def test_build_rejects_packet_id_for_qos_zero() -> None:
    with pytest.raises(MQTTError):
        PublishPacket.build("topic", b"data", 1, False, QOS_0, False)


def test_build_rejects_missing_packet_id_for_qos_one() -> None:
    with pytest.raises(MQTTError):
        PublishPacket.build("topic", b"data", None, False, QOS_1, False)


def test_set_qos_and_packet_id_updates_coupled_fields() -> None:
    variable_header = PublishVariableHeader("topic")
    payload = PublishPayload(b"data")
    packet = PublishPacket(variable_header=variable_header, payload=payload)

    packet.set_qos_and_packet_id(QOS_2, 10)

    assert packet.qos == QOS_2
    assert packet.packet_id == 10
    assert packet.to_bytes() == b"\x34\x0e\x00\x05topic\x00\x0a\x00data"


def test_setting_dup_before_qos_raises() -> None:
    packet = PublishPacket()

    with pytest.raises(MQTTError):
        packet.dup_flag = True


def test_build_sets_qos_and_packet_id_before_dup_flag() -> None:
    packet = PublishPacket.build("topic", b"data", 10, True, QOS_1, False)

    assert packet.dup_flag is True
    assert packet.qos == QOS_1
    assert packet.packet_id == 10
    assert packet.to_bytes() == b"\x3a\x0e\x00\x05topic\x00\x0a\x00data"


@given(data=st.binary())
def test_publish_decode_never_crashes(make_reader, data: bytes) -> None:
    try:
        asyncio.run(PublishPacket.from_stream(make_reader(data)))
    except (AMQTTError, MQTTError):
        pass
