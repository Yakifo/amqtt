import asyncio
from unittest.mock import AsyncMock

from hypothesis import given, strategies as st
import pytest

from amqtt.adapters import BufferReader, BufferWriter
from amqtt.errors import AMQTTError, MQTTError
from amqtt.mqtt3.packet import MQTTFixedHeader, PUBLISH
from amqtt.mqtt5.connack import ConnackPacket
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    ASSIGNED_CLIENT_IDENTIFIER,
    CONTENT_TYPE,
    PACKET_CONNACK,
    REASON_STRING,
    SESSION_EXPIRY_INTERVAL,
)
from amqtt.mqtt5.protocol.broker_handler import BrokerProtocolHandler
from amqtt.mqtt5.reason_codes import ReasonCode
from amqtt.session import Session


def test_decode_spec_example_minimal_success() -> None:
    data = b"\x20\x03\x00\x00\x00"

    packet = asyncio.run(ConnackPacket.from_stream(BufferReader(data)))

    assert packet.session_present is False
    assert packet.reason_code is ReasonCode.SUCCESS
    assert packet.properties == Properties(packet_name=PACKET_CONNACK)
    assert packet.to_bytes() == data


def test_success_reason_code_metadata() -> None:
    assert ReasonCode.SUCCESS == 0
    assert ReasonCode.SUCCESS.is_error() is False
    assert ReasonCode.SUCCESS.description == "Success"


def test_connack_round_trip_with_success_properties() -> None:
    properties = Properties(packet_name=PACKET_CONNACK)
    properties.set(SESSION_EXPIRY_INTERVAL, 300)
    properties.set(ASSIGNED_CLIENT_IDENTIFIER, "client-1")
    properties.set(REASON_STRING, "ok")
    expected = b"\x20\x18\x01\x00\x15\x11\x00\x00\x01\x2c\x12\x00\x08client-1\x1f\x00\x02ok"

    packet = ConnackPacket.build(True, ReasonCode.SUCCESS, properties)
    decoded = asyncio.run(ConnackPacket.from_stream(BufferReader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.session_present is True
    assert decoded.reason_code is ReasonCode.SUCCESS
    assert decoded.properties == properties
    assert decoded.to_bytes() == expected


@pytest.mark.asyncio
async def test_minimal_success_connack_can_be_sent_to_client() -> None:
    writer = BufferWriter()
    packet = ConnackPacket.build()

    await packet.to_stream(writer)

    assert writer.get_buffer() == b"\x20\x03\x00\x00\x00"


@pytest.mark.asyncio
async def test_broker_handler_can_send_success_connack() -> None:
    plugins_manager = AsyncMock()
    handler = BrokerProtocolHandler(plugins_manager, loop=asyncio.get_running_loop())
    session = Session()
    session.parent = 1
    writer = BufferWriter()
    handler.attach(session, BufferReader(b""), writer)

    await handler.mqtt_connack_authorize(True)

    assert writer.get_buffer() == b"\x20\x03\x01\x00\x00"
    plugins_manager.fire_event.assert_awaited()


def test_incorrect_fixed_header() -> None:
    header = MQTTFixedHeader(PUBLISH, 0x00)
    with pytest.raises(AMQTTError):
        ConnackPacket(fixed=header)


def test_fixed_header_reserved_flags_raise() -> None:
    header = MQTTFixedHeader(0x02, 0x01)
    with pytest.raises(MQTTError):
        ConnackPacket(fixed=header)


def test_acknowledge_reserved_flags_raise() -> None:
    data = b"\x20\x03\x02\x00\x00"

    with pytest.raises(MQTTError):
        asyncio.run(ConnackPacket.from_stream(BufferReader(data)))


def test_non_success_reason_code_is_deferred() -> None:
    data = b"\x20\x03\x00\x80\x00"

    with pytest.raises(MQTTError):
        asyncio.run(ConnackPacket.from_stream(BufferReader(data)))


def test_build_rejects_non_connack_properties() -> None:
    properties = Properties()
    properties.set(CONTENT_TYPE, "text/plain")

    with pytest.raises(MQTTError):
        ConnackPacket.build(properties=properties)


@given(st.binary())
def test_connack_decode_never_crashes(data: bytes) -> None:
    try:
        asyncio.run(ConnackPacket.from_stream(BufferReader(data)))
    except (AMQTTError, MQTTError):
        pass
