import asyncio

from hypothesis import given, settings, strategies as st

from amqtt.adapters import BufferReader
from amqtt.errors import AMQTTError, CodecError, MQTTError, NoDataError
from amqtt.mqtt import packet_class
from amqtt.mqtt.packet import MQTTFixedHeader


EXPECTED_DECODE_ERRORS = (AMQTTError, CodecError, MQTTError, NoDataError, ValueError)


async def _decode_fixed_header(data: bytes) -> MQTTFixedHeader | None:
    return await MQTTFixedHeader.from_stream(BufferReader(data))


async def _decode_packet(data: bytes) -> None:
    reader = BufferReader(data)
    fixed_header = await MQTTFixedHeader.from_stream(reader)
    if fixed_header is None:
        return

    packet = packet_class(fixed_header)
    await packet.from_stream(reader, fixed_header=fixed_header)


@settings(max_examples=200, deadline=None)
@given(st.binary(max_size=8))
def test_fuzz_fixed_header_decode(data: bytes) -> None:
    try:
        fixed_header = asyncio.run(_decode_fixed_header(data))
    except EXPECTED_DECODE_ERRORS:
        return

    if fixed_header is None:
        return

    assert 0 <= fixed_header.packet_type <= 0x0F
    assert 0 <= fixed_header.flags <= 0x0F
    assert 0 <= fixed_header.remaining_length <= 268_435_455
    assert 2 <= fixed_header.bytes_length <= 5


@settings(max_examples=250, deadline=None)
@given(st.binary(max_size=64))
def test_fuzz_packet_decode_dispatch(data: bytes) -> None:
    try:
        asyncio.run(_decode_packet(data))
    except EXPECTED_DECODE_ERRORS:
        return
