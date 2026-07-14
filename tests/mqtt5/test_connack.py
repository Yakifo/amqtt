import asyncio

from hypothesis import given, strategies as st
import pytest

from amqtt.errors import AMQTTError, MQTTError
from amqtt.mqtt3.packet import MQTTFixedHeader, PUBLISH
from amqtt.mqtt5.connack import ConnackPacket
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    ASSIGNED_CLIENT_IDENTIFIER,
    CONTENT_TYPE,
    MAXIMUM_PACKET_SIZE,
    MAXIMUM_QOS,
    PACKET_CONNACK,
    PACKET_PUBLISH,
    REASON_STRING,
    RECEIVE_MAXIMUM,
    RETAIN_AVAILABLE,
    SESSION_EXPIRY_INTERVAL,
    SHARED_SUBSCRIPTION_AVAILABLE,
    SUBSCRIPTION_IDENTIFIER_AVAILABLE,
    TOPIC_ALIAS_MAXIMUM,
    WILDCARD_SUBSCRIPTION_AVAILABLE,
)
from amqtt.mqtt5.reason_codes import ReasonCode
from amqtt.session import MQTT5_DEFAULT_RECEIVE_MAXIMUM, MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM


def test_decode_spec_example_minimal_success(make_reader) -> None:
    data = b"\x20\x03\x00\x00\x00"

    packet = asyncio.run(ConnackPacket.from_stream(make_reader(data)))

    assert packet.session_present is False
    assert packet.reason_code is ReasonCode.SUCCESS
    assert packet.properties == Properties(packet_name=PACKET_CONNACK)
    assert packet.to_bytes() == data


def test_success_reason_code_metadata() -> None:
    assert ReasonCode.SUCCESS == 0
    assert ReasonCode.SUCCESS.is_error() is False
    assert ReasonCode.SUCCESS.description == "Success"


def test_connack_round_trip_with_success_properties(make_reader) -> None:
    properties = Properties(packet_name=PACKET_CONNACK)
    properties.set(SESSION_EXPIRY_INTERVAL, 300)
    properties.set(ASSIGNED_CLIENT_IDENTIFIER, "client-1")
    properties.set(REASON_STRING, "ok")
    expected = b"\x20\x18\x01\x00\x15\x11\x00\x00\x01\x2c\x12\x00\x08client-1\x1f\x00\x02ok"

    packet = ConnackPacket.build(True, ReasonCode.SUCCESS, properties)
    decoded = asyncio.run(ConnackPacket.from_stream(make_reader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.session_present is True
    assert decoded.reason_code is ReasonCode.SUCCESS
    assert decoded.properties == properties
    assert decoded.to_bytes() == expected


@pytest.mark.asyncio
async def test_minimal_success_connack_can_be_sent_to_client(mock_client_handler) -> None:
    writer = mock_client_handler.writer
    packet = ConnackPacket.build()

    await packet.to_stream(writer)

    assert writer.get_buffer() == b"\x20\x03\x00\x00\x00"


@pytest.mark.asyncio
async def test_broker_handler_can_send_success_connack(mock_broker_handler, make_reader) -> None:
    handler = mock_broker_handler
    handler.session.parent = 1

    await handler.mqtt_connack_authorize(True)

    packet = await ConnackPacket.from_stream(make_reader(handler.writer.get_buffer()))
    assert packet.session_present is True
    assert packet.reason_code is ReasonCode.SUCCESS
    assert packet.properties.get(RECEIVE_MAXIMUM) == MQTT5_DEFAULT_RECEIVE_MAXIMUM
    assert packet.properties.get(TOPIC_ALIAS_MAXIMUM) == MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM
    assert packet.properties.get(RETAIN_AVAILABLE) == 1
    assert packet.properties.get(WILDCARD_SUBSCRIPTION_AVAILABLE) == 1
    assert packet.properties.get(SUBSCRIPTION_IDENTIFIER_AVAILABLE) == 0
    assert packet.properties.get(SHARED_SUBSCRIPTION_AVAILABLE) == 0
    handler.plugins_manager.fire_event.assert_awaited()


@pytest.mark.asyncio
async def test_broker_handler_success_connack_uses_configured_limits(mock_broker_handler, make_reader) -> None:
    handler = mock_broker_handler
    handler.config.receive_maximum = 128
    handler.config.topic_alias_maximum = 7
    handler.config.maximum_packet_size = 1024
    handler.config.maximum_qos = 1
    handler.config.retain_available = False
    handler.config.wildcard_subscription_available = False
    handler.config.subscription_identifier_available = True
    handler.config.shared_subscription_available = True

    await handler.mqtt_connack_authorize(True)

    packet = await ConnackPacket.from_stream(make_reader(handler.writer.get_buffer()))
    assert packet.properties.get(RECEIVE_MAXIMUM) == 128
    assert packet.properties.get(TOPIC_ALIAS_MAXIMUM) == 7
    assert packet.properties.get(MAXIMUM_PACKET_SIZE) == 1024
    assert packet.properties.get(MAXIMUM_QOS) == 1
    assert packet.properties.get(RETAIN_AVAILABLE) == 0
    assert packet.properties.get(WILDCARD_SUBSCRIPTION_AVAILABLE) == 0
    assert packet.properties.get(SUBSCRIPTION_IDENTIFIER_AVAILABLE) == 1
    assert packet.properties.get(SHARED_SUBSCRIPTION_AVAILABLE) == 1


@pytest.mark.asyncio
async def test_broker_handler_success_connack_includes_assigned_client_id(mock_broker_handler, make_reader) -> None:
    handler = mock_broker_handler
    handler.session.client_id = "generated-client"
    handler.session.client_id_is_generated = True

    await handler.mqtt_connack_authorize(True)

    packet = await ConnackPacket.from_stream(make_reader(handler.writer.get_buffer()))
    assert packet.properties.get(ASSIGNED_CLIENT_IDENTIFIER) == "generated-client"


@pytest.mark.asyncio
async def test_broker_handler_can_send_not_authorized_connack(mock_broker_handler) -> None:
    handler = mock_broker_handler
    handler.session.parent = 1

    await handler.mqtt_connack_authorize(False)

    assert handler.writer.get_buffer() == b"\x20\x03\x00\x87\x00"
    handler.plugins_manager.fire_event.assert_awaited()


def test_incorrect_fixed_header() -> None:
    header = MQTTFixedHeader(PUBLISH, 0x00)
    with pytest.raises(AMQTTError):
        ConnackPacket(fixed=header)


def test_fixed_header_reserved_flags_raise() -> None:
    header = MQTTFixedHeader(0x02, 0x01)
    with pytest.raises(MQTTError):
        ConnackPacket(fixed=header)


def test_acknowledge_reserved_flags_raise(make_reader) -> None:
    data = b"\x20\x03\x02\x00\x00"

    with pytest.raises(MQTTError):
        asyncio.run(ConnackPacket.from_stream(make_reader(data)))


def test_connack_accepts_connect_error_reason_code(make_reader) -> None:
    data = b"\x20\x03\x00\x80\x00"

    packet = asyncio.run(ConnackPacket.from_stream(make_reader(data)))

    assert packet.reason_code is ReasonCode.UNSPECIFIED_ERROR
    assert packet.reason_code.is_error() is True
    assert packet.to_bytes() == data


def test_connack_accepts_reason_code_without_packet_specific_validation(make_reader) -> None:
    data = bytes([0x20, 0x03, 0x00, int(ReasonCode.NO_SUBSCRIPTION_EXISTED), 0x00])

    packet = asyncio.run(ConnackPacket.from_stream(make_reader(data)))

    assert packet.reason_code is ReasonCode.NO_SUBSCRIPTION_EXISTED
    assert packet.to_bytes() == data


def test_connack_rejects_unknown_reason_code(make_reader) -> None:
    data = b"\x20\x03\x00\x03\x00"

    with pytest.raises(MQTTError):
        asyncio.run(ConnackPacket.from_stream(make_reader(data)))


def test_build_rejects_non_connack_properties() -> None:
    properties = Properties(packet_name=PACKET_PUBLISH)
    properties.set(CONTENT_TYPE, "text/plain")

    with pytest.raises(MQTTError):
        ConnackPacket.build(properties=properties)


@given(data=st.binary())
def test_connack_decode_never_crashes(make_reader, data: bytes) -> None:
    try:
        asyncio.run(ConnackPacket.from_stream(make_reader(data)))
    except (AMQTTError, MQTTError):
        pass
