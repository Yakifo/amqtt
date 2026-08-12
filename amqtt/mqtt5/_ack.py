"""Shared MQTT 5.0 PUBACK/PUBREC/PUBREL/PUBCOMP packet helpers."""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar
from typing_extensions import Self

from amqtt.codecs_amqtt import bytes_to_int, int_to_bytes, read_exact
from amqtt.errors import AMQTTError, CodecError, MQTTError, NoDataError
from amqtt.mqtt3.packet import MQTTFixedHeader, MQTTPacket, MQTTVariableHeader
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.reason_codes import ReasonCode

if TYPE_CHECKING:
    from amqtt.adapters import ReaderAdapter
    from amqtt.mqtt5.property_ids import PacketName


class AcknowledgementVariableHeader(MQTTVariableHeader):
    """MQTT 5.0 acknowledgement variable header shared by PUBACK/PUBREC/PUBREL/PUBCOMP."""

    PACKET_NAME: ClassVar[PacketName]

    __slots__ = ("packet_id", "properties", "reason_code")

    def __init__(
        self,
        packet_id: int,
        reason_code: ReasonCode = ReasonCode.SUCCESS,
        properties: Properties | None = None,
    ) -> None:
        super().__init__()
        self.packet_id = packet_id
        try:
            self.reason_code = ReasonCode(reason_code)
        except ValueError as exc:
            msg = f"Unknown MQTT 5.0 reason code: {reason_code}"
            raise MQTTError(msg) from exc
        self.properties = Properties.for_packet(self.PACKET_NAME, properties)
        self.validate()

    def validate(self) -> None:
        """Validate packet identifier constraints."""
        if not 1 <= self.packet_id <= 0xFFFF:
            msg = "[MQTT-2.2.1-3] QoS acknowledgement packets require a non-zero Packet Identifier."
            raise MQTTError(msg)

    def to_bytes(self) -> bytes | bytearray:
        """Encode packet id, optional reason code, and optional properties."""
        self.validate()
        out = bytearray(int_to_bytes(self.packet_id, 2))
        if self.reason_code is ReasonCode.SUCCESS and self.properties.is_empty():
            return out
        out.append(int(self.reason_code))
        if not self.properties.is_empty():
            out.extend(self.properties.encode())
        return out

    @classmethod
    async def from_stream(cls: type[Self], reader: ReaderAdapter, fixed_header: MQTTFixedHeader) -> Self:
        """Decode the acknowledgement variable header from a stream."""
        if fixed_header.remaining_length < 2:
            msg = f"MQTT 5.0 {cls.PACKET_NAME} remaining length must include a Packet Identifier"
            raise MQTTError(msg)
        body = await read_exact(reader, fixed_header.remaining_length, f"{cls.PACKET_NAME} packet body")
        return cls.from_bytes(body)

    @classmethod
    def from_bytes(cls: type[Self], data: bytes | bytearray) -> Self:
        """Decode the acknowledgement variable header from packet-body bytes."""
        if len(data) < 2:
            msg = f"MQTT 5.0 {cls.PACKET_NAME} remaining length must include a Packet Identifier"
            raise MQTTError(msg)

        packet_id = bytes_to_int(bytes(data[0:2]))
        reason_code = ReasonCode.SUCCESS
        properties = Properties(packet_name=cls.PACKET_NAME)

        if len(data) >= 3:
            try:
                reason_code = ReasonCode(data[2])
            except ValueError as exc:
                msg = f"Unknown MQTT 5.0 reason code: {data[2]}"
                raise MQTTError(msg) from exc
        if len(data) >= 4:
            properties = Properties.decode(data[3:], packet_name=cls.PACKET_NAME)

        return cls(packet_id, reason_code, properties)

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"{type(self).__name__}(packet_id={self.packet_id!r}, "
            f"reason_code={self.reason_code!r}, properties={self.properties!r})"
        )


_AckVariableHeader = TypeVar("_AckVariableHeader", bound=AcknowledgementVariableHeader)


class AcknowledgementPacket(MQTTPacket[_AckVariableHeader, None, MQTTFixedHeader], Generic[_AckVariableHeader]):
    """Base MQTT 5.0 acknowledgement packet."""

    VARIABLE_HEADER: type[_AckVariableHeader]
    PAYLOAD = None
    PACKET_TYPE: ClassVar[int]
    PACKET_NAME: ClassVar[PacketName]
    EXPECTED_FLAGS: ClassVar[int]

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: _AckVariableHeader | None = None,
        payload: None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(self.PACKET_TYPE, self.EXPECTED_FLAGS)
        else:
            self._validate_fixed_header(fixed)
            header = fixed
        super().__init__(header, variable_header, payload)

    @classmethod
    def _validate_fixed_header(cls, fixed_header: MQTTFixedHeader) -> None:
        if fixed_header.packet_type != cls.PACKET_TYPE:
            msg = f"Invalid fixed packet type {fixed_header.packet_type} for {cls.__name__} init"
            raise AMQTTError(msg) from None
        if fixed_header.flags != cls.EXPECTED_FLAGS:
            msg = f"Invalid fixed header flags for MQTT 5.0 {cls.PACKET_NAME}"
            raise MQTTError(msg)

    @classmethod
    def build(
        cls,
        packet_id: int,
        reason_code: ReasonCode = ReasonCode.SUCCESS,
        properties: Properties | None = None,
    ) -> Self:
        """Build an outgoing MQTT 5.0 acknowledgement packet."""
        variable_header = cls.VARIABLE_HEADER(packet_id, reason_code, properties)  # pylint: disable=not-callable
        return cls(variable_header=variable_header)

    @classmethod
    async def from_stream(
        cls,
        reader: ReaderAdapter,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: _AckVariableHeader | None = None,
    ) -> Self:
        """Decode an MQTT 5.0 acknowledgement packet from a stream."""
        if fixed_header is None:
            try:
                fixed_header = await cls.FIXED_HEADER.from_stream(reader)
            except (CodecError, MQTTError, NoDataError, struct.error) as exc:
                msg = f"Malformed MQTT 5.0 {cls.PACKET_NAME} fixed header"
                raise MQTTError(msg) from exc
        if fixed_header is None:
            msg = f"No MQTT 5.0 {cls.PACKET_NAME} fixed header available"
            raise MQTTError(msg)
        cls._validate_fixed_header(fixed_header)

        if variable_header is None:
            try:
                variable_header = await cls.VARIABLE_HEADER.from_stream(reader, fixed_header)
            except (CodecError, MQTTError, NoDataError, struct.error) as exc:
                msg = f"Malformed MQTT 5.0 {cls.PACKET_NAME} packet"
                raise MQTTError(msg) from exc

        return cls(fixed_header, variable_header)

    @property
    def packet_id(self) -> int:
        """Return the Packet Identifier."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.packet_id

    @packet_id.setter
    def packet_id(self, val: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.packet_id = val
        self.variable_header.validate()

    @property
    def reason_code(self) -> ReasonCode:
        """Return the acknowledgement reason code."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.reason_code

    @reason_code.setter
    def reason_code(self, val: ReasonCode) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.reason_code = ReasonCode(val)

    @property
    def properties(self) -> Properties:
        """Return the acknowledgement properties."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.properties
