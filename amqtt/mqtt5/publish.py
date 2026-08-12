"""MQTT 5.0 PUBLISH packet (MQTT 5.0 section 3.3)."""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING
from typing_extensions import Self

from amqtt.codecs_amqtt import (
    bytes_to_int,
    decode_packet_id,
    decode_string,
    decode_string_from_bytes,
    encode_string,
    int_to_bytes,
    read_exact,
    require_exact,
)
from amqtt.errors import AMQTTError, CodecError, MQTTError, NoDataError
from amqtt.mqtt3.packet import PUBLISH, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import PACKET_PUBLISH, TOPIC_ALIAS

if TYPE_CHECKING:
    from asyncio import StreamReader

    from amqtt.adapters import ReaderAdapter

PUBLISH_DUP_FLAG = 0x08
PUBLISH_RETAIN_FLAG = 0x01
PUBLISH_QOS_MASK = 0x06


class PublishVariableHeader(MQTTVariableHeader):
    """MQTT 5.0 PUBLISH variable header (MQTT 5.0 section 3.3.2)."""

    __slots__ = ("_wire_length", "packet_id", "properties", "topic_name")

    def __init__(
        self,
        topic_name: str,
        packet_id: int | None = None,
        properties: Properties | None = None,
        *,
        wire_length: int | None = None,
    ) -> None:
        super().__init__()
        self.topic_name = topic_name
        self.packet_id = packet_id
        self.properties = Properties.for_packet(PACKET_PUBLISH, properties)
        self._wire_length = wire_length
        self._validate()

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"{type(self).__name__}(topic={self.topic_name!r}, packet_id={self.packet_id!r}, "
            f"properties={self.properties!r})"
        )

    def _validate(self) -> None:
        # [MQTT-3.3.2-2] Topic Name in a PUBLISH packet cannot contain wildcards.
        if "#" in self.topic_name or "+" in self.topic_name:
            msg = "[MQTT-3.3.2-2] Topic name in the PUBLISH Packet MUST NOT contain wildcard characters."
            raise MQTTError(msg)
        # MQTT 5.0 section 3.3.2.1 allows an empty Topic Name only when Topic Alias is present.
        if self.topic_name == "" and not self.properties.has(TOPIC_ALIAS):
            msg = "PUBLISH Topic Name cannot be zero length without a Topic Alias"
            raise MQTTError(msg)
        if self.packet_id is not None and not 1 <= self.packet_id <= 0xFFFF:
            msg = "[MQTT-2.2.1-3] QoS > 0 PUBLISH packets require a non-zero Packet Identifier."
            raise MQTTError(msg)

    def to_bytes(self) -> bytes | bytearray:
        """Encode the MQTT 5.0 PUBLISH variable header."""
        self._validate()
        out = bytearray()
        # [MQTT-3.3.2-1] Topic Name is the first PUBLISH variable-header field.
        out.extend(encode_string(self.topic_name))
        if self.packet_id is not None:
            out.extend(int_to_bytes(self.packet_id, 2))
        out.extend(self.properties.encode())
        return out

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter, fixed_header: MQTTFixedHeader) -> Self:
        """Decode a MQTT 5.0 PUBLISH variable header from a stream."""
        topic_name = await decode_string(reader, strict=True, field_name="PUBLISH Topic Name")
        qos = (fixed_header.flags & PUBLISH_QOS_MASK) >> 1
        packet_id = await decode_packet_id(reader) if qos else None
        properties = await Properties.from_stream(reader, packet_name=PACKET_PUBLISH)
        wire_length = len(encode_string(topic_name)) + (2 if packet_id is not None else 0) + len(properties.encode())
        return cls(topic_name, packet_id, properties, wire_length=wire_length)

    @classmethod
    def from_bytes(cls, data: bytes | bytearray, offset: int, end: int, qos: int) -> tuple[Self, int]:
        """Decode a MQTT 5.0 PUBLISH variable header from packet-body bytes."""
        topic_name, offset = decode_string_from_bytes(data, offset, end, field_name="PUBLISH Topic Name")
        packet_id = None
        if qos:
            require_exact(offset, end, 2, "PUBLISH Packet Identifier")
            packet_id = bytes_to_int(bytes(data[offset:offset + 2]))
            offset += 2
        properties, offset = Properties.from_bytes(data, offset, end, packet_name=PACKET_PUBLISH, field_name="PUBLISH")
        return cls(topic_name, packet_id, properties, wire_length=offset), offset

    @property
    def bytes_length(self) -> int:
        """Return the number of bytes consumed by this variable header."""
        if self._wire_length is not None:
            return self._wire_length
        return len(self.to_bytes())


class PublishPayload(MQTTPayload[MQTTVariableHeader]):
    """MQTT 5.0 PUBLISH payload (MQTT 5.0 section 3.3.3)."""

    __slots__ = ("data",)

    def __init__(self, data: bytes | bytearray | None = None) -> None:
        super().__init__()
        self.data = bytes(data) if data is not None else None

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"{type(self).__name__}(data={self.data!r})"

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: MQTTVariableHeader | None = None,
    ) -> bytes:
        """Encode the MQTT 5.0 PUBLISH payload."""
        return self.data if self.data is not None else b""

    @classmethod
    async def from_stream(
        cls,
        reader: StreamReader | ReaderAdapter,
        fixed_header: MQTTFixedHeader | None,
        variable_header: MQTTVariableHeader | None,
    ) -> Self:
        """Decode a MQTT 5.0 PUBLISH payload from a stream."""
        if fixed_header is None:
            msg = "PUBLISH fixed header is not set"
            raise MQTTError(msg)
        if variable_header is None:
            msg = "PUBLISH variable header is not set"
            raise MQTTError(msg)

        data_length = fixed_header.remaining_length - variable_header.bytes_length
        if data_length < 0:
            msg = "PUBLISH variable header exceeds remaining length"
            raise MQTTError(msg)
        data = await read_exact(reader, data_length, "PUBLISH Payload")
        return cls(data)

    @classmethod
    def from_bytes(cls, data: bytes | bytearray, offset: int, end: int) -> Self:
        """Decode a MQTT 5.0 PUBLISH payload from packet-body bytes."""
        if offset > end:
            msg = "PUBLISH payload offset exceeds packet body"
            raise MQTTError(msg)
        return cls(bytes(data[offset:end]))


class PublishPacket(MQTTPacket[PublishVariableHeader, PublishPayload, MQTTFixedHeader]):
    """MQTT 5.0 PUBLISH packet (MQTT 5.0 section 3.3)."""

    VARIABLE_HEADER = PublishVariableHeader
    PAYLOAD = PublishPayload

    DUP_FLAG = PUBLISH_DUP_FLAG
    RETAIN_FLAG = PUBLISH_RETAIN_FLAG
    QOS_FLAG = PUBLISH_QOS_MASK

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PublishVariableHeader | None = None,
        payload: PublishPayload | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(PUBLISH, 0x00)
        elif fixed.packet_type != PUBLISH:
            msg = f"Invalid fixed packet type {fixed.packet_type} for PublishPacket init"
            raise AMQTTError(msg) from None
        else:
            header = fixed

        super().__init__(header, variable_header, payload)
        self.validate()

    @classmethod
    def build(
        cls,
        topic_name: str,
        message: bytes | bytearray,
        packet_id: int | None,
        dup_flag: bool,
        qos: int | None,
        retain: bool,
        properties: Properties | None = None,
    ) -> Self:
        """Build an outgoing MQTT 5.0 PUBLISH packet."""
        variable_header = PublishVariableHeader(topic_name, None, properties)
        payload = PublishPayload(message)
        packet = cls(variable_header=variable_header, payload=payload)
        packet.set_qos_and_packet_id(qos or 0, packet_id)
        packet.retain_flag = retain
        packet.dup_flag = dup_flag
        return packet

    @classmethod
    async def from_stream(
        cls,
        reader: ReaderAdapter,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: PublishVariableHeader | None = None,
    ) -> Self:
        """Decode a MQTT 5.0 PUBLISH packet from a stream."""
        if fixed_header is None:
            try:
                fixed_header = await cls.FIXED_HEADER.from_stream(reader)
            except (CodecError, MQTTError, NoDataError, struct.error) as exc:
                msg = "Malformed MQTT 5.0 PUBLISH fixed header"
                raise MQTTError(msg) from exc
        if fixed_header is None:
            msg = "No MQTT 5.0 PUBLISH fixed header available"
            raise MQTTError(msg)
        if fixed_header.packet_type != PUBLISH:
            msg = f"Invalid fixed packet type {fixed_header.packet_type} for PublishPacket init"
            raise AMQTTError(msg) from None

        try:
            if variable_header is None:
                body = await read_exact(reader, fixed_header.remaining_length, "PUBLISH packet body")
                variable_header, payload_offset = cls.VARIABLE_HEADER.from_bytes(
                    body,
                    0,
                    len(body),
                    (fixed_header.flags & PUBLISH_QOS_MASK) >> 1,
                )
                payload = cls.PAYLOAD.from_bytes(body, payload_offset, len(body))
            else:
                payload = await cls.PAYLOAD.from_stream(reader, fixed_header, variable_header)
        except (CodecError, MQTTError, NoDataError, struct.error) as exc:
            msg = "Malformed MQTT 5.0 PUBLISH packet"
            raise MQTTError(msg) from exc

        return cls(fixed_header, variable_header, payload)

    def set_flags(self, dup_flag: bool = False, qos: int = 0, retain_flag: bool = False) -> None:
        """Set the PUBLISH fixed-header flags."""
        packet_id = self.variable_header.packet_id if self.variable_header is not None else None
        self.set_qos_and_packet_id(qos, packet_id)
        self.retain_flag = retain_flag
        self.dup_flag = dup_flag

    def validate(self) -> None:
        """Validate the PUBLISH fixed header and Packet Identifier."""
        qos = self.qos
        if qos == 3:
            msg = "[MQTT-3.3.1-4] PUBLISH QoS value 3 is reserved."
            raise MQTTError(msg)
        if qos == 0 and self.dup_flag:
            msg = "[MQTT-3.3.1-2] DUP flag must be 0 for QoS 0 PUBLISH packets."
            raise MQTTError(msg)
        if self.variable_header is None:
            if qos > 0:
                msg = "QoS 1 and QoS 2 PUBLISH packets require a Packet Identifier."
                raise MQTTError(msg)
            return
        packet_id = self.variable_header.packet_id
        if qos == 0 and packet_id is not None:
            msg = "[MQTT-2.2.1-2] QoS 0 PUBLISH packets MUST NOT contain a Packet Identifier."
            raise MQTTError(msg)
        if qos > 0 and packet_id is None:
            msg = "QoS 1 and QoS 2 PUBLISH packets require a Packet Identifier."
            raise MQTTError(msg)
        if packet_id is not None and not 1 <= packet_id <= 0xFFFF:
            msg = "[MQTT-2.2.1-3] QoS > 0 PUBLISH packets require a non-zero Packet Identifier."
            raise MQTTError(msg)

    def set_qos_and_packet_id(self, qos: int, packet_id: int | None) -> None:
        """Set QoS and Packet Identifier as one validated operation.

        In MQTT 5.0, the QoS and Packet Identifier are related:
         - QoS 0 must not have a packet identifier,
         - packet identifier is required for QoS 1 and 2
        """
        if qos not in {0, 1, 2}:
            msg = "[MQTT-3.3.1-4] PUBLISH QoS value 3 is reserved."
            raise MQTTError(msg)
        if self.variable_header is None and packet_id is not None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.fixed_header.flags &= ~self.QOS_FLAG
        self.fixed_header.flags |= qos << 1
        if self.variable_header is not None:
            self.variable_header.packet_id = packet_id
        self.validate()

    def _set_header_flag(self, val: bool, mask: int) -> None:
        if val:
            self.fixed_header.flags |= mask
        else:
            self.fixed_header.flags &= ~mask
        self.validate()

    def _get_header_flag(self, mask: int) -> bool:
        return bool(self.fixed_header.flags & mask)

    @property
    def dup_flag(self) -> bool:
        """Return whether this PUBLISH packet is a redelivery attempt."""
        return self._get_header_flag(self.DUP_FLAG)

    @dup_flag.setter
    def dup_flag(self, val: bool) -> None:
        self._set_header_flag(val, self.DUP_FLAG)

    @property
    def retain_flag(self) -> bool:
        """Return whether this PUBLISH packet should be retained."""
        return self._get_header_flag(self.RETAIN_FLAG)

    @retain_flag.setter
    def retain_flag(self, val: bool) -> None:
        self._set_header_flag(val, self.RETAIN_FLAG)

    @property
    def qos(self) -> int:
        """Return the PUBLISH QoS level."""
        return (self.fixed_header.flags & self.QOS_FLAG) >> 1

    @qos.setter
    def qos(self, val: int) -> None:
        packet_id = self.variable_header.packet_id if self.variable_header is not None else None
        self.set_qos_and_packet_id(val, packet_id)

    @property
    def packet_id(self) -> int | None:
        """Return the PUBLISH Packet Identifier, if present."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.packet_id

    @packet_id.setter
    def packet_id(self, val: int | None) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.set_qos_and_packet_id(self.qos, val)

    @property
    def data(self) -> bytes | None:
        """Return the PUBLISH payload data."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.data

    @data.setter
    def data(self, data: bytes | bytearray) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.data = bytes(data)

    @property
    def topic_name(self) -> str:
        """Return the PUBLISH Topic Name."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.topic_name

    @topic_name.setter
    def topic_name(self, name: str) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.topic_name = name

    @property
    def properties(self) -> Properties:
        """Return the PUBLISH properties."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.properties
