"""Atheris fuzz target for MQTT packet parsing."""

import asyncio
import sys

import atheris

with atheris.instrument_imports():
    from amqtt.adapters import BufferReader
    from amqtt.errors import AMQTTError, CodecError, MQTTError, NoDataError
    from amqtt.mqtt import packet_class
    from amqtt.mqtt.packet import MQTTFixedHeader


EXPECTED_DECODE_ERRORS = (AMQTTError, CodecError, MQTTError, NoDataError, ValueError)


async def _decode_packet(data: bytes) -> None:
    reader = BufferReader(data)
    fixed_header = await MQTTFixedHeader.from_stream(reader)
    if fixed_header is None:
        return

    packet = packet_class(fixed_header)
    await packet.from_stream(reader, fixed_header=fixed_header)


def TestOneInput(data: bytes) -> None:  # noqa: N802
    """Exercise MQTT packet decoding with arbitrary input bytes."""
    try:
        asyncio.run(_decode_packet(data))
    except EXPECTED_DECODE_ERRORS:
        return


def main() -> None:
    """Run the Atheris fuzz loop."""
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
