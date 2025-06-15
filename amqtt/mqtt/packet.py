from abc import ABC, abstractmethod
import asyncio

try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc

from struct import unpack
from typing import Generic
from typing_extensions import Self, TypeVar

from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.codecs_amqtt import bytes_to_hex_str, decode_packet_id, int_to_bytes, read_or_raise
from amqtt.errors import CodecError, MQTTError, NoDataError

RESERVED_0 = 0x00
CONNECT = 0x01
CONNACK = 0x02
PUBLISH = 0x03
PUBACK = 0x04
PUBREC = 0x05
PUBREL = 0x06
PUBCOMP = 0x07
SUBSCRIBE = 0x08
SUBACK = 0x09
UNSUBSCRIBE = 0x0A
UNSUBACK = 0x0B
PINGREQ = 0x0C
PINGRESP = 0x0D
DISCONNECT = 0x0E
RESERVED_15 = 0x0F


class MQTTFixedHeader:
    """Represents the fixed header of an MQTT packet."""

    __slots__ = ("flags", "packet_type", "remaining_length")

    def __init__(self, packet_type: int, flags: int = 0, length: int = 0) -> None:
        self.packet_type = packet_type
        self.flags = flags
        self.remaining_length = length

    def to_bytes(self) -> bytes:
        """Encode the fixed header to bytes."""

        def encode_remaining_length(length: int) -> bytes:
            """Encode the remaining length as per MQTT protocol."""
            encoded = bytearray()
            while True:
                length_byte = length % 0x80
                length //= 0x80
                if length > 0:
                    length_byte |= 0x80
                encoded.append(length_byte)
                if length <= 0:
                    break
            return bytes(encoded)

        try:
            packet_type_flags = (self.packet_type << 4) | self.flags
            encoded_length = encode_remaining_length(self.remaining_length)
            return bytes([packet_type_flags]) + encoded_length
        except OverflowError as exc:
            msg = f"Fixed header encoding failed: {exc}"
            raise CodecError(msg) from exc

    async def to_stream(self, writer: WriterAdapter) -> None:
        """Write the fixed header to the stream."""
        writer.write(self.to_bytes())

    @property
    def bytes_length(self) -> int:
        return len(self.to_bytes())

    @classmethod
    async def from_stream(cls: type[Self], reader: ReaderAdapter) -> "Self | None":
        """Decode a fixed header from the stream."""

        async def decode_remaining_length() -> int:
            """Decode the remaining length from the stream."""
            multiplier: int
            value: int
            multiplier, value = 1, 0
            buffer = bytearray()
            while True:
                encoded_byte = await reader.read(1)
                byte_value = unpack("!B", encoded_byte)[0]
                buffer.append(byte_value)
                value += (byte_value & 0x7F) * multiplier
                if (byte_value & 0x80) == 0:
                    break
                multiplier *= 128
                if multiplier > 128**3:
                    msg = f"Invalid remaining length bytes:{bytes_to_hex_str(buffer)}, packet_type={packet_type}"
                    raise MQTTError(msg)
            return value

        try:
            byte1 = await read_or_raise(reader, 1)
            int1 = unpack("!B", byte1)[0]
            packet_type = (int1 & 0xF0) >> 4
            flags = int1 & 0x0F
            remaining_length = await decode_remaining_length()
            return cls(packet_type, flags, remaining_length)
        except NoDataError:
            return None

    def __repr__(self) -> str:
        """Return a string representation of the MQTTFixedHeader object."""
        return f"{self.__class__.__name__}(packet_type={self.packet_type}, flags={self.flags}, length={self.remaining_length})"


_FH = TypeVar("_FH", bound=MQTTFixedHeader)


class MQTTVariableHeader(ABC):
    """Abstract base class for MQTT variable headers."""

    async def to_stream(self, writer: asyncio.StreamWriter) -> None:
        writer.write(self.to_bytes())
        await writer.drain()

    @abstractmethod
    def to_bytes(self) -> bytes | bytearray:
        """Serialize the variable header to bytes."""

    @property
    def bytes_length(self) -> int:
        return len(self.to_bytes())

    @classmethod
    @abstractmethod
    async def from_stream(cls: type[Self], reader: ReaderAdapter, fixed_header: MQTTFixedHeader) -> Self:
        pass


class PacketIdVariableHeader(MQTTVariableHeader):
    """Represents a variable header containing a packet ID."""

    __slots__ = ("packet_id",)

    def __init__(self, packet_id: int) -> None:
        super().__init__()
        self.packet_id = packet_id

    def to_bytes(self) -> bytes:
        return int_to_bytes(self.packet_id, 2)

    @classmethod
    async def from_stream(
        cls: type[Self],
        reader: ReaderAdapter,
        _: MQTTFixedHeader | None = None,
    ) -> Self:
        packet_id = await decode_packet_id(reader)
        return cls(packet_id)

    def __repr__(self) -> str:
        """Return a string representation of the PacketIdVariableHeader object."""
        return f"{self.__class__.__name__}(packet_id={self.packet_id})"


_VH = TypeVar("_VH", bound=MQTTVariableHeader | None)


class MQTTPayload(Generic[_VH], ABC):
    """Abstract base class for MQTT payloads."""

    async def to_stream(self, writer: asyncio.StreamWriter) -> None:
        writer.write(self.to_bytes())
        await writer.drain()

    @abstractmethod
    def to_bytes(self, fixed_header: MQTTFixedHeader | None = None, variable_header: _VH | None = None) -> bytes | bytearray:
        pass

    @classmethod
    @abstractmethod
    async def from_stream(
        cls: type[Self],
        reader: asyncio.StreamReader | ReaderAdapter,
        fixed_header: MQTTFixedHeader | None,
        variable_header: _VH | None,
    ) -> Self:
        pass


_P = TypeVar("_P", bound=MQTTPayload[MQTTVariableHeader] | None)


class MQTTPacket(Generic[_VH, _P, _FH]):
    """Represents an MQTT packet."""

    __slots__ = ("fixed_header", "payload", "protocol_ts", "variable_header")

    VARIABLE_HEADER: type[_VH] | None = None
    PAYLOAD: type[_P] | None = None
    FIXED_HEADER: type[_FH] = MQTTFixedHeader  # type: ignore [assignment]

    def __init__(self, fixed: _FH, variable_header: _VH | None = None, payload: _P | None = None) -> None:
        self.fixed_header = fixed
        self.variable_header = variable_header
        self.payload = payload
        self.protocol_ts: datetime | None = None

    async def to_stream(self, writer: WriterAdapter) -> None:
        """Write the entire packet to the stream."""
        writer.write(self.to_bytes())
        await writer.drain()
        self.protocol_ts = datetime.now(UTC)

    def to_bytes(self) -> bytes:
        """Serialize the packet into bytes."""
        variable_header_bytes = self.variable_header.to_bytes() if self.variable_header is not None else b""
        payload_bytes = self.payload.to_bytes(self.fixed_header, self.variable_header) if self.payload is not None else b""

        fixed_header_bytes = b""
        if self.fixed_header:
            self.fixed_header.remaining_length = len(variable_header_bytes) + len(payload_bytes)
            fixed_header_bytes = self.fixed_header.to_bytes()

        return fixed_header_bytes + variable_header_bytes + payload_bytes

    @classmethod
    async def from_stream(
        cls: type[Self],
        reader: ReaderAdapter,
        fixed_header: _FH | None = None,
        variable_header: _VH | None = None,
    ) -> Self:
        """Decode an MQTT packet from the stream."""
        if fixed_header is None:
            fixed_header = await cls.FIXED_HEADER.from_stream(reader)

        if cls.VARIABLE_HEADER and variable_header is None:
            variable_header = await cls.VARIABLE_HEADER.from_stream(reader, fixed_header)

        if cls.PAYLOAD and fixed_header:
            payload = await cls.PAYLOAD.from_stream(reader, fixed_header, variable_header)
        else:
            payload = None

        if fixed_header and not variable_header and not payload:
            instance = cls(fixed_header)
        elif fixed_header and not payload:
            instance = cls(fixed_header, variable_header)
        else:
            instance = cls(fixed_header, variable_header, payload)
        instance.protocol_ts = datetime.now(UTC)
        return instance

    @property
    def bytes_length(self) -> int:
        return len(self.to_bytes())

    def __repr__(self) -> str:
        """Return a string representation of the packet."""
        return (
            f"{self.__class__.__name__}(ts={self.protocol_ts}, "
            f"fixed={self.fixed_header}, variable={self.variable_header}, payload={self.payload})"
        )
