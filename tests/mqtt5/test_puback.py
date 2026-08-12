import asyncio

from hypothesis import given, strategies as st
import pytest

from amqtt.errors import AMQTTError, MQTTError
from amqtt.mqtt3.puback import PubackPacket as PubackV3Packet
from amqtt.mqtt3.pubcomp import PubcompPacket as PubcompV3Packet
from amqtt.mqtt3.pubrec import PubrecPacket as PubrecV3Packet
from amqtt.mqtt3.pubrel import PubrelPacket as PubrelV3Packet
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    PACKET_CONNECT,
    PACKET_PUBACK,
    PACKET_PUBCOMP,
    PACKET_PUBREC,
    PACKET_PUBREL,
    REASON_STRING,
    SESSION_EXPIRY_INTERVAL,
)
from amqtt.mqtt5.puback import PubackPacket
from amqtt.mqtt5.pubcomp import PubcompPacket
from amqtt.mqtt5.pubrec import PubrecPacket
from amqtt.mqtt5.pubrel import PubrelPacket
from amqtt.mqtt5.reason_codes import ReasonCode

ACK_PACKET_CASES = [
    pytest.param(PubackPacket, PACKET_PUBACK, b"\x40", id="PUBACK"),
    pytest.param(PubrecPacket, PACKET_PUBREC, b"\x50", id="PUBREC"),
    pytest.param(PubrelPacket, PACKET_PUBREL, b"\x62", id="PUBREL"),
    pytest.param(PubcompPacket, PACKET_PUBCOMP, b"\x70", id="PUBCOMP"),
]

V3_ACK_PACKET_CASES = [
    pytest.param(PubackV3Packet, b"\x40\x02\x00\x0a", id="PUBACK"),
    pytest.param(PubrecV3Packet, b"\x50\x02\x00\x0a", id="PUBREC"),
    pytest.param(PubrelV3Packet, b"\x62\x02\x00\x0a", id="PUBREL"),
    pytest.param(PubcompV3Packet, b"\x70\x02\x00\x0a", id="PUBCOMP"),
]


@pytest.mark.parametrize(("packet_cls", "packet_name", "fixed_header"), ACK_PACKET_CASES)
def test_decode_spec_example_short_form(packet_cls, packet_name: str, fixed_header: bytes, make_reader) -> None:
    data = fixed_header + b"\x02\x00\x0a"

    packet = asyncio.run(packet_cls.from_stream(make_reader(data)))

    assert packet.packet_id == 10
    assert packet.reason_code is ReasonCode.SUCCESS
    assert packet.properties == Properties(packet_name=packet_name)
    assert packet.to_bytes() == data


@pytest.mark.parametrize(("packet_cls", "packet_name", "fixed_header"), ACK_PACKET_CASES)
def test_short_form_round_trip(packet_cls, packet_name: str, fixed_header: bytes, make_reader) -> None:
    expected = fixed_header + b"\x02\x00\x0a"

    packet = packet_cls.build(10)
    decoded = asyncio.run(packet_cls.from_stream(make_reader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.packet_id == 10
    assert decoded.reason_code is ReasonCode.SUCCESS
    assert decoded.properties == Properties(packet_name=packet_name)
    assert decoded.to_bytes() == expected


@pytest.mark.parametrize(("packet_cls", "packet_name", "fixed_header"), ACK_PACKET_CASES)
def test_full_form_round_trip(packet_cls, packet_name: str, fixed_header: bytes, make_reader) -> None:
    properties = Properties(packet_name=packet_name)
    properties.set(REASON_STRING, "nope")
    expected = fixed_header + b"\x0b\x00\x0a\x92\x07\x1f\x00\x04nope"

    packet = packet_cls.build(10, ReasonCode.PACKET_IDENTIFIER_NOT_FOUND, properties)
    decoded = asyncio.run(packet_cls.from_stream(make_reader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.packet_id == 10
    assert decoded.reason_code is ReasonCode.PACKET_IDENTIFIER_NOT_FOUND
    assert decoded.reason_code.is_error() is True
    assert decoded.properties.get(REASON_STRING) == "nope"
    assert decoded.properties == properties
    assert decoded.to_bytes() == expected


@pytest.mark.parametrize(("packet_cls", "packet_name", "fixed_header"), ACK_PACKET_CASES)
def test_reason_code_without_properties_round_trip(packet_cls, packet_name: str, fixed_header: bytes, make_reader) -> None:
    expected = fixed_header + b"\x03\x00\x0a\x10"

    packet = packet_cls.build(10, ReasonCode.NO_MATCHING_SUBSCRIBERS)
    decoded = asyncio.run(packet_cls.from_stream(make_reader(packet.to_bytes())))

    assert packet.to_bytes() == expected
    assert decoded.packet_id == 10
    assert decoded.reason_code is ReasonCode.NO_MATCHING_SUBSCRIBERS
    assert decoded.properties == Properties(packet_name=packet_name)
    assert decoded.to_bytes() == expected


@pytest.mark.parametrize(("packet_cls", "packet_name", "fixed_header"), ACK_PACKET_CASES)
def test_parser_accepts_full_success_form(packet_cls, packet_name: str, fixed_header: bytes, make_reader) -> None:
    data = fixed_header + b"\x04\x00\x0a\x00\x00"

    packet = asyncio.run(packet_cls.from_stream(make_reader(data)))

    assert packet.packet_id == 10
    assert packet.reason_code is ReasonCode.SUCCESS
    assert packet.properties == Properties(packet_name=packet_name)
    assert packet.to_bytes() == fixed_header + b"\x02\x00\x0a"


@pytest.mark.parametrize(("packet_cls", "data"), V3_ACK_PACKET_CASES)
def test_mqtt3_ack_parsing_is_unchanged(packet_cls, data: bytes, make_reader) -> None:
    packet = asyncio.run(packet_cls.from_stream(make_reader(data)))

    assert packet.packet_id == 10
    assert packet.to_bytes() == data


@pytest.mark.parametrize(
    ("packet_cls", "data"),
    [
        pytest.param(PubackPacket, b"\x40\x01\x00", id="short-body"),
        pytest.param(PubackPacket, b"\x40\x02\x00\x00", id="zero-packet-id"),
        pytest.param(PubackPacket, b"\x40\x03\x00\x01\x03", id="unknown-reason-code"),
        pytest.param(PubackPacket, b"\x40\x05\x00\x01\x80\x05\x1f", id="malformed-properties"),
        pytest.param(PubrelPacket, b"\x60\x02\x00\x01", id="pubrel-invalid-flags"),
    ],
)
def test_malformed_ack_input_raises(packet_cls, data: bytes, make_reader) -> None:
    with pytest.raises(MQTTError):
        asyncio.run(packet_cls.from_stream(make_reader(data)))


def test_incorrect_fixed_header_raises() -> None:
    with pytest.raises(AMQTTError):
        PubackPacket(fixed=PubrecPacket.build(10).fixed_header)


def test_build_rejects_non_ack_properties() -> None:
    properties = Properties(packet_name=PACKET_CONNECT)
    properties.set(SESSION_EXPIRY_INTERVAL, 60)

    with pytest.raises(MQTTError):
        PubackPacket.build(10, properties=properties)


@pytest.mark.parametrize("prop", ["packet_id", "reason_code", "properties"])
def test_empty_variable_header(prop: str) -> None:
    packet = PubackPacket()

    with pytest.raises(ValueError):
        assert getattr(packet, prop) is not None


@pytest.mark.parametrize("prop", ["packet_id", "reason_code"])
def test_empty_variable_header_setter(prop: str) -> None:
    packet = PubackPacket()

    with pytest.raises(ValueError):
        setattr(packet, prop, 10)


@pytest.mark.parametrize(("packet_cls", "_packet_name", "_fixed_header"), ACK_PACKET_CASES)
@given(data=st.binary())
def test_ack_decode_never_crashes(packet_cls, _packet_name: str, _fixed_header: bytes, make_reader, data: bytes) -> None:
    try:
        asyncio.run(packet_cls.from_stream(make_reader(data)))
    except (AMQTTError, MQTTError):
        pass
