import asyncio

import pytest
from hypothesis import given, strategies as st

from amqtt.adapters import BufferReader
from amqtt.errors import MQTTError
from amqtt.mqtt3.packet import CONNECT, MQTTFixedHeader
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    ASSIGNED_CLIENT_IDENTIFIER,
    AUTHENTICATION_DATA,
    AUTHENTICATION_METHOD,
    CONTENT_TYPE,
    CORRELATION_DATA,
    MAXIMUM_PACKET_SIZE,
    MAXIMUM_QOS,
    MESSAGE_EXPIRY_INTERVAL,
    PACKET_CONNACK,
    PACKET_CONNECT,
    PACKET_PUBLISH,
    PACKET_SUBSCRIBE,
    PAYLOAD_FORMAT_INDICATOR,
    PROPERTY_DEFINITIONS,
    PropertyWireType,
    REASON_STRING,
    RECEIVE_MAXIMUM,
    REQUEST_PROBLEM_INFORMATION,
    REQUEST_RESPONSE_INFORMATION,
    RESPONSE_INFORMATION,
    RESPONSE_TOPIC,
    RETAIN_AVAILABLE,
    SERVER_KEEP_ALIVE,
    SERVER_REFERENCE,
    SESSION_EXPIRY_INTERVAL,
    SHARED_SUBSCRIPTION_AVAILABLE,
    SUBSCRIPTION_IDENTIFIER,
    SUBSCRIPTION_IDENTIFIER_AVAILABLE,
    TOPIC_ALIAS,
    TOPIC_ALIAS_MAXIMUM,
    USER_PROPERTY,
    WILDCARD_SUBSCRIPTION_AVAILABLE,
    WILL_DELAY_INTERVAL,
)


def sample_value(wire_type: PropertyWireType):
    if wire_type is PropertyWireType.BYTE:
        return 1
    if wire_type is PropertyWireType.TWO_BYTE_INTEGER:
        return 42
    if wire_type is PropertyWireType.FOUR_BYTE_INTEGER:
        return 300
    if wire_type is PropertyWireType.VARIABLE_BYTE_INTEGER:
        return 321
    if wire_type is PropertyWireType.UTF8_STRING:
        return "value"
    if wire_type is PropertyWireType.UTF8_STRING_PAIR:
        return ("key", "value")
    if wire_type is PropertyWireType.BINARY_DATA:
        return b"value"
    raise AssertionError(wire_type)


@pytest.mark.parametrize("identifier", sorted(PROPERTY_DEFINITIONS))
def test_property_round_trip_for_every_identifier(identifier: int):
    properties = Properties()
    properties.set(identifier, sample_value(PROPERTY_DEFINITIONS[identifier].wire_type))

    decoded = Properties.decode(properties.encode())

    assert decoded == properties


@pytest.mark.parametrize(
    ("identifier", "value", "expected_wire"),
    [
        (PAYLOAD_FORMAT_INDICATOR, 1, b"\x01\x01"),
        (MESSAGE_EXPIRY_INTERVAL, 60, b"\x02\x00\x00\x00\x3c"),
        (CONTENT_TYPE, "text/plain", b"\x03\x00\x0atext/plain"),
        (RESPONSE_TOPIC, "reply/to", b"\x08\x00\x08reply/to"),
        (CORRELATION_DATA, b"abc", b"\x09\x00\x03abc"),
        (SUBSCRIPTION_IDENTIFIER, 42, b"\x0b\x2a"),
        (SESSION_EXPIRY_INTERVAL, 300, b"\x11\x00\x00\x01\x2c"),
        (ASSIGNED_CLIENT_IDENTIFIER, "client-1", b"\x12\x00\x08client-1"),
        (SERVER_KEEP_ALIVE, 30, b"\x13\x00\x1e"),
        (AUTHENTICATION_METHOD, "token", b"\x15\x00\x05token"),
        (AUTHENTICATION_DATA, b"secret", b"\x16\x00\x06secret"),
        (REQUEST_PROBLEM_INFORMATION, 1, b"\x17\x01"),
        (WILL_DELAY_INTERVAL, 5, b"\x18\x00\x00\x00\x05"),
        (REQUEST_RESPONSE_INFORMATION, 1, b"\x19\x01"),
        (RESPONSE_INFORMATION, "info", b"\x1a\x00\x04info"),
        (SERVER_REFERENCE, "mqtt://other", b"\x1c\x00\x0cmqtt://other"),
        (REASON_STRING, "ok", b"\x1f\x00\x02ok"),
        (RECEIVE_MAXIMUM, 10, b"\x21\x00\x0a"),
        (TOPIC_ALIAS_MAXIMUM, 4, b"\x22\x00\x04"),
        (TOPIC_ALIAS, 2, b"\x23\x00\x02"),
        (MAXIMUM_QOS, 1, b"\x24\x01"),
        (RETAIN_AVAILABLE, 1, b"\x25\x01"),
        (USER_PROPERTY, ("k", "v"), b"\x26\x00\x01k\x00\x01v"),
        (MAXIMUM_PACKET_SIZE, 1024, b"\x27\x00\x00\x04\x00"),
        (WILDCARD_SUBSCRIPTION_AVAILABLE, 1, b"\x28\x01"),
        (SUBSCRIPTION_IDENTIFIER_AVAILABLE, 1, b"\x29\x01"),
        (SHARED_SUBSCRIPTION_AVAILABLE, 1, b"\x2a\x01"),
    ],
)
def test_property_wire_bytes(identifier: int, value, expected_wire: bytes):
    properties = Properties()
    properties.set(identifier, value)

    encoded = properties.encode()

    assert encoded == bytes([len(expected_wire)]) + expected_wire
    assert Properties.decode(encoded) == properties


def test_decode_spec_example_empty_properties():
    assert Properties().encode() == b"\x00"
    assert Properties.decode(b"\x00") == Properties()


def test_duplicate_non_repeatable_property_raises():
    properties = Properties()
    properties.set(CONTENT_TYPE, "text/plain")

    with pytest.raises(MQTTError):
        properties.set(CONTENT_TYPE, "application/json")


def test_duplicate_user_properties_are_preserved_in_order():
    properties = Properties()
    properties.set(USER_PROPERTY, ("key", "one"))
    properties.set(USER_PROPERTY, ("key", "two"))

    decoded = Properties.decode(properties.encode())

    assert decoded.get(USER_PROPERTY) == [("key", "one"), ("key", "two")]


def test_decode_duplicate_non_repeatable_property_raises():
    duplicate_content_type = b"\x16\x03\x00\x04text\x03\x00\x04json"

    with pytest.raises(MQTTError):
        Properties.decode(duplicate_content_type)


def test_packet_context_rejects_property_not_valid_for_packet():
    properties = Properties(packet_name=PACKET_CONNECT)

    with pytest.raises(MQTTError):
        properties.set(CONTENT_TYPE, "text/plain")

    content_type_empty_string = b"\x03\x03\x00\x00"
    with pytest.raises(MQTTError):
        Properties.decode(content_type_empty_string, packet_name=PACKET_CONNECT)


def test_subscription_identifier_repeatability_depends_on_packet_context():
    subscribe_properties = Properties(packet_name=PACKET_SUBSCRIBE)
    subscribe_properties.set(SUBSCRIPTION_IDENTIFIER, 1)

    with pytest.raises(MQTTError):
        subscribe_properties.set(SUBSCRIPTION_IDENTIFIER, 2)

    duplicate_subscription_ids = b"\x04\x0b\x01\x0b\x02"
    with pytest.raises(MQTTError):
        Properties.decode(duplicate_subscription_ids, packet_name=PACKET_SUBSCRIBE)

    publish_properties = Properties(packet_name=PACKET_PUBLISH)
    publish_properties.set(SUBSCRIPTION_IDENTIFIER, 1)
    publish_properties.set(SUBSCRIPTION_IDENTIFIER, 2)

    assert publish_properties.get(SUBSCRIPTION_IDENTIFIER) == [1, 2]
    assert Properties.decode(duplicate_subscription_ids, packet_name=PACKET_PUBLISH) == publish_properties


@pytest.mark.parametrize(
    ("identifier", "value", "packet_name"),
    [
        (MAXIMUM_PACKET_SIZE, 0, PACKET_CONNECT),
        (RECEIVE_MAXIMUM, 0, PACKET_CONNECT),
        (SUBSCRIPTION_IDENTIFIER, 0, PACKET_SUBSCRIBE),
        (TOPIC_ALIAS, 0, PACKET_PUBLISH),
        (REQUEST_PROBLEM_INFORMATION, 2, PACKET_CONNECT),
        (REQUEST_RESPONSE_INFORMATION, 2, PACKET_CONNECT),
        (MAXIMUM_QOS, 2, PACKET_CONNACK),
    ],
)
def test_protocol_value_constraints_are_enforced_on_set(identifier: int, value: int, packet_name: str):
    properties = Properties(packet_name=packet_name)

    with pytest.raises(MQTTError):
        properties.set(identifier, value)


@pytest.mark.parametrize(
    ("data", "packet_name"),
    [
        (b"\x05\x27\x00\x00\x00\x00", PACKET_CONNECT),
        (b"\x03\x21\x00\x00", PACKET_CONNECT),
        (b"\x02\x0b\x00", PACKET_SUBSCRIBE),
        (b"\x03\x23\x00\x00", PACKET_PUBLISH),
        (b"\x02\x17\x02", PACKET_CONNECT),
        (b"\x02\x19\x02", PACKET_CONNECT),
        (b"\x02\x24\x02", PACKET_CONNACK),
    ],
)
def test_protocol_value_constraints_are_enforced_on_decode(data: bytes, packet_name: str):
    with pytest.raises(MQTTError):
        Properties.decode(data, packet_name=packet_name)


@pytest.mark.parametrize("data", [b"", b"\x02\x03", b"\x01\xff", b"\x05\x03\x00\xffbad", b"\x00\x01"])
def test_malformed_properties_raise_mqtt_error(data: bytes):
    with pytest.raises(MQTTError):
        Properties.decode(data)


@given(st.binary())
def test_properties_decode_never_crashes(data: bytes):
    try:
        Properties.decode(data)
    except MQTTError:
        pass


def test_mqtt3_fixed_header_uses_shared_variable_byte_integer_helpers():
    header = MQTTFixedHeader(CONNECT, 0x00, 16_384)
    data = header.to_bytes()
    stream = BufferReader(data)

    decoded = asyncio.run(MQTTFixedHeader.from_stream(stream))

    assert data == b"\x10\x80\x80\x01"
    assert decoded is not None
    assert decoded.remaining_length == 16_384
