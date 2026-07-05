"""MQTT 5.0 CONNACK packet (§3.2)."""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING
from typing_extensions import Self

from amqtt.codecs_amqtt import read_or_raise
from amqtt.errors import AMQTTError, CodecError, MQTTError, NoDataError
from amqtt.mqtt3.packet import CONNACK, MQTTFixedHeader, MQTTPacket, MQTTVariableHeader
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import PACKET_CONNACK
from amqtt.mqtt5.reason_codes import ReasonCode

if TYPE_CHECKING:
    from amqtt.adapters import ReaderAdapter


class ConnackVariableHeader(MQTTVariableHeader):
    """MQTT 5.0 CONNACK variable header (§3.2.2)."""

    __slots__ = ("properties", "reason_code", "session_present")

    def __init__(
        self,
        session_present: bool = False,
        reason_code: ReasonCode = ReasonCode.SUCCESS,
        properties: Properties | None = None,
        ) -> None:
        super().__init__()
        self.session_present = session_present
        self.reason_code = self.ensure_success_reason_code(reason_code)
        self.properties = self.connack_properties(properties)

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter, fixed_header: MQTTFixedHeader) -> Self:
        """Decode a CONNACK variable header from a stream."""
        if fixed_header.remaining_length < 3:
            msg = "MQTT 5.0 CONNACK remaining length must include flags, reason code, and properties"
            raise MQTTError(msg)

        data = await read_or_raise(reader, fixed_header.remaining_length)
        if len(data) != fixed_header.remaining_length:
            msg = "MQTT 5.0 CONNACK data shorter than remaining length"
            raise MQTTError(msg)

        flags = data[0]
        # [MQTT-3.2.2-1] Connect Acknowledge Flags bits 7-1 are reserved.
        if flags & 0xFE:
            msg = "[MQTT-3.2.2-1] CONNACK reserved acknowledge flags must be 0"
            raise MQTTError(msg)

        reason_code = cls.ensure_success_reason_code(data[1])
        properties = Properties.decode(data[2:], packet_name=PACKET_CONNACK)
        return cls(bool(flags & 0x01), reason_code, properties)

    def to_bytes(self) -> bytes | bytearray:
        """Encode the CONNACK variable header."""
        out = bytearray()
        # [MQTT-3.2.2-1] Bits 7-1 are reserved; bit 0 is Session Present.
        out.append(1 if self.session_present else 0)
        out.append(self.reason_code)
        out.extend(self.properties.encode())
        return out

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"{type(self).__name__}(session_present={self.session_present}, "
            f"reason_code={self.reason_code!r}, properties={self.properties!r})"
        )

    @staticmethod
    def ensure_success_reason_code(reason_code: ReasonCode | int) -> ReasonCode:
        try:
            return ReasonCode(reason_code)
        except ValueError as exc:
            msg = "Only MQTT 5.0 CONNACK Success reason code is implemented"
            raise MQTTError(msg) from exc

    @staticmethod
    def connack_properties(properties: Properties | None) -> Properties:
        connack_properties = Properties(packet_name=PACKET_CONNACK)
        if properties is None:
            return connack_properties

        for identifier, value in properties.items():
            connack_properties.set(identifier, value)
        return connack_properties


class ConnackPacket(MQTTPacket[ConnackVariableHeader, None, MQTTFixedHeader]):
    """MQTT 5.0 CONNACK packet (§3.2)."""

    VARIABLE_HEADER = ConnackVariableHeader
    PAYLOAD = None

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: ConnackVariableHeader | None = None,
        payload: None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(CONNACK, 0x00)
        elif fixed.packet_type != CONNACK:
            msg = f"Invalid fixed packet type {fixed.packet_type} for ConnackPacket init"
            raise AMQTTError(msg) from None
        elif fixed.flags != 0x00:
            msg = "Invalid fixed header flags for MQTT 5.0 CONNACK"
            raise MQTTError(msg)
        else:
            header = fixed

        super().__init__(header, variable_header, payload)

    @classmethod
    def build(
        cls,
        session_present: bool = False,
        reason_code: ReasonCode = ReasonCode.SUCCESS,
        properties: Properties | None = None,
    ) -> Self:
        """Build an outgoing MQTT 5.0 CONNACK packet."""
        variable_header = ConnackVariableHeader(session_present, reason_code, properties)
        return cls(variable_header=variable_header)

    @classmethod
    async def from_stream(
        cls,
        reader: ReaderAdapter,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: ConnackVariableHeader | None = None,
    ) -> Self:
        """Decode an MQTT 5.0 CONNACK packet from a stream."""
        if fixed_header is None:
            try:
                fixed_header = await cls.FIXED_HEADER.from_stream(reader)
            except (CodecError, MQTTError, NoDataError, struct.error) as exc:
                msg = "Malformed MQTT 5.0 CONNACK fixed header"
                raise MQTTError(msg) from exc
        if fixed_header is None:
            msg = "No MQTT 5.0 CONNACK fixed header available"
            raise MQTTError(msg)
        if fixed_header.packet_type != CONNACK:
            msg = f"Invalid fixed packet type {fixed_header.packet_type} for ConnackPacket init"
            raise AMQTTError(msg) from None
        if fixed_header.flags != 0x00:
            msg = "Invalid fixed header flags for MQTT 5.0 CONNACK"
            raise MQTTError(msg)

        if variable_header is None:
            variable_header = await cls.VARIABLE_HEADER.from_stream(reader, fixed_header)

        return cls(fixed_header, variable_header)

    @property
    def reason_code(self) -> ReasonCode:
        """Return the CONNACK reason code."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.reason_code

    @property
    def session_present(self) -> bool:
        """Return the CONNACK Session Present flag."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.session_present

    @property
    def properties(self) -> Properties:
        """Return the CONNACK properties."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.properties
