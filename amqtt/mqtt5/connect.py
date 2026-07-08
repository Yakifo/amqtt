"""MQTT 5.0 CONNECT packet (§3.1)."""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING
from typing_extensions import Self

from amqtt.codecs_amqtt import (
    bytes_to_int,
    decode_string,
    decode_string_from_bytes,
    encode_data_with_length,
    encode_string,
    int_to_bytes,
    read_exact,
    require_exact,
)
from amqtt.errors import AMQTTError, CodecError, MQTTError, NoDataError
from amqtt.mqtt3.packet import CONNECT, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_codecs import decode_data_from_bytes
from amqtt.mqtt5.property_ids import PACKET_CONNECT, PACKET_WILL

if TYPE_CHECKING:
    from asyncio import StreamReader

    from amqtt.adapters import ReaderAdapter


class ConnectVariableHeader(MQTTVariableHeader):
    """MQTT 5.0 CONNECT variable header (§3.1.2)."""

    __slots__ = ("_wire_length", "flags", "keep_alive", "properties", "proto_level", "proto_name")

    USERNAME_FLAG = 0x80
    PASSWORD_FLAG = 0x40
    WILL_RETAIN_FLAG = 0x20
    WILL_FLAG = 0x04
    WILL_QOS_MASK = 0x18
    CLEAN_START_FLAG = 0x02
    RESERVED_FLAG = 0x01

    def __init__(
        self,
        connect_flags: int = 0x00,
        keep_alive: int = 0,
        proto_name: str = "MQTT",
        proto_level: int = 0x05,
        properties: Properties | None = None,
        *,
        wire_length: int | None = None,
    ) -> None:
        super().__init__()
        self.proto_name = proto_name
        self.proto_level = proto_level
        self.flags = connect_flags
        self.keep_alive = keep_alive
        self.properties = Properties.for_packet(PACKET_CONNECT, properties)
        self._wire_length = wire_length
        self._validate()

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"{type(self).__name__}(proto_name={self.proto_name!r}, proto_level={self.proto_level}, "
            f"flags={hex(self.flags)}, keep_alive={self.keep_alive}, properties={self.properties!r})"
        )

    def _set_flag(self, val: bool, mask: int) -> None:
        if val:
            self.flags |= mask
        else:
            self.flags &= ~mask
        self._wire_length = None

    def _get_flag(self, mask: int) -> bool:
        return bool(self.flags & mask)

    def _validate(self) -> None:
        # [MQTT-3.1.2-1] The protocol name must be the UTF-8 String "MQTT".
        if self.proto_name != "MQTT":
            msg = f'[MQTT-3.1.2-1] Incorrect protocol name: "{self.proto_name}"'
            raise MQTTError(msg)
        # [MQTT-3.1.2-2] MQTT 5.0 uses Protocol Version byte 5.
        if self.proto_level != 0x05:
            msg = f"[MQTT-3.1.2-2] Incorrect MQTT 5.0 protocol level: {self.proto_level}"
            raise MQTTError(msg)
        # [MQTT-3.1.2-3] The CONNECT reserved flag must be 0.
        if self.reserved_flag:
            msg = "[MQTT-3.1.2-3] CONNECT reserved flag must be set to 0"
            raise MQTTError(msg)
        # [MQTT-3.1.2-11] Will QoS must be 0 when the Will Flag is 0.
        if not self.will_flag and self.will_qos != 0:
            msg = "[MQTT-3.1.2-11] CONNECT Will QoS must be 0 when Will Flag is 0"
            raise MQTTError(msg)
        # [MQTT-3.1.2-12] Will QoS value 3 is a malformed packet.
        if self.will_flag and self.will_qos == 3:
            msg = "[MQTT-3.1.2-12] CONNECT Will QoS must be 0, 1, or 2"
            raise MQTTError(msg)
        # [MQTT-3.1.2-13] Will Retain must be 0 when the Will Flag is 0.
        if not self.will_flag and self.will_retain_flag:
            msg = "[MQTT-3.1.2-13] CONNECT Will Retain must be 0 when Will Flag is 0"
            raise MQTTError(msg)

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter, _: MQTTFixedHeader) -> Self:
        """Decode a MQTT 5.0 CONNECT variable header from a stream."""
        proto_name = await decode_string(reader, strict=True, field_name="CONNECT Protocol Name")
        proto_level = bytes_to_int(await read_exact(reader, 1, "CONNECT Protocol Level"))
        flags = bytes_to_int(await read_exact(reader, 1, "CONNECT Flags"))
        keep_alive = bytes_to_int(await read_exact(reader, 2, "CONNECT Keep Alive"))
        properties = await Properties.from_stream(reader, packet_name=PACKET_CONNECT)
        wire_length = 2 + len(proto_name.encode("utf-8")) + 1 + 1 + 2 + len(properties.encode())
        return cls(flags, keep_alive, proto_name, proto_level, properties, wire_length=wire_length)

    @classmethod
    def from_bytes(cls, data: bytes | bytearray, end: int) -> tuple[Self, int]:
        """Decode a MQTT 5.0 CONNECT variable header from packet-body bytes."""
        offset = 0
        proto_name, offset = decode_string_from_bytes(data, offset, end, field_name="CONNECT Protocol Name")
        require_exact(offset, end, 4, "CONNECT variable header")
        proto_level = data[offset]
        offset += 1
        flags = data[offset]
        offset += 1
        keep_alive = bytes_to_int(bytes(data[offset:offset + 2]))
        offset += 2
        properties, offset = Properties.from_bytes(data, offset, end, packet_name=PACKET_CONNECT, field_name="CONNECT")
        return cls(flags, keep_alive, proto_name, proto_level, properties, wire_length=offset), offset

    def to_bytes(self) -> bytes | bytearray:
        """Encode the MQTT 5.0 CONNECT variable header."""
        self._validate()
        out = bytearray()
        out.extend(encode_string(self.proto_name))
        out.append(self.proto_level)
        out.append(self.flags)
        out.extend(int_to_bytes(self.keep_alive, 2))
        out.extend(self.properties.encode())
        return out

    @property
    def bytes_length(self) -> int:
        """Return the number of bytes consumed by this variable header."""
        if self._wire_length is not None:
            return self._wire_length
        return len(self.to_bytes())

    @property
    def username_flag(self) -> bool:
        """Return whether the payload contains a User Name field."""
        return self._get_flag(self.USERNAME_FLAG)

    @username_flag.setter
    def username_flag(self, val: bool) -> None:
        self._set_flag(val, self.USERNAME_FLAG)

    @property
    def password_flag(self) -> bool:
        """Return whether the payload contains a Password field."""
        return self._get_flag(self.PASSWORD_FLAG)

    @password_flag.setter
    def password_flag(self, val: bool) -> None:
        self._set_flag(val, self.PASSWORD_FLAG)

    @property
    def will_retain_flag(self) -> bool:
        """Return whether the Will Message should be retained."""
        return self._get_flag(self.WILL_RETAIN_FLAG)

    @will_retain_flag.setter
    def will_retain_flag(self, val: bool) -> None:
        self._set_flag(val, self.WILL_RETAIN_FLAG)

    @property
    def will_flag(self) -> bool:
        """Return whether the payload contains Will fields."""
        return self._get_flag(self.WILL_FLAG)

    @will_flag.setter
    def will_flag(self, val: bool) -> None:
        self._set_flag(val, self.WILL_FLAG)

    @property
    def clean_start_flag(self) -> bool:
        """Return the MQTT 5.0 Clean Start flag."""
        return self._get_flag(self.CLEAN_START_FLAG)

    @clean_start_flag.setter
    def clean_start_flag(self, val: bool) -> None:
        self._set_flag(val, self.CLEAN_START_FLAG)

    @property
    def reserved_flag(self) -> bool:
        """Return whether the reserved CONNECT flag bit is set."""
        return self._get_flag(self.RESERVED_FLAG)

    @reserved_flag.setter
    def reserved_flag(self, val: bool) -> None:
        self._set_flag(val, self.RESERVED_FLAG)

    @property
    def will_qos(self) -> int:
        """Return the Will QoS value from the CONNECT flags."""
        return (self.flags & self.WILL_QOS_MASK) >> 3

    @will_qos.setter
    def will_qos(self, val: int) -> None:
        self.flags &= ~self.WILL_QOS_MASK
        self.flags |= val << 3
        self._wire_length = None


class ConnectPayload(MQTTPayload[ConnectVariableHeader]):
    """MQTT 5.0 CONNECT payload (§3.1.3)."""

    __slots__ = (
        "client_id",
        "client_id_is_random",
        "password",
        "username",
        "will_message",
        "will_properties",
        "will_topic",
    )

    def __init__(
        self,
        client_id: str | None = "",
        will_topic: str | None = None,
        will_message: bytes | bytearray | None = None,
        username: str | None = None,
        password: bytes | bytearray | None = None,
        will_properties: Properties | None = None,
    ) -> None:
        super().__init__()
        self.client_id_is_random = False
        self.client_id = client_id
        self.will_topic = will_topic
        self.will_message = will_message
        self.username = username
        self.password = password
        self.will_properties = Properties.for_packet(PACKET_WILL, will_properties)

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return (
            f"{type(self).__name__}(client_id={self.client_id!r}, will_topic={self.will_topic!r}, "
            f"will_message={self.will_message!r}, username={self.username!r}, password={self.password!r}, "
            f"will_properties={self.will_properties!r})"
        )

    @classmethod
    async def from_stream(
        cls,
        reader: StreamReader | ReaderAdapter,
        fixed_header: MQTTFixedHeader | None,
        variable_header: ConnectVariableHeader | None,
    ) -> Self:
        """Decode a MQTT 5.0 CONNECT payload from a stream."""
        if fixed_header is None:
            msg = "CONNECT fixed header is not set"
            raise MQTTError(msg)
        if variable_header is None:
            msg = "CONNECT variable header is not set"
            raise MQTTError(msg)

        payload_length = fixed_header.remaining_length - variable_header.bytes_length
        if payload_length < 0:
            msg = "CONNECT variable header exceeds remaining length"
            raise MQTTError(msg)
        data = await read_exact(reader, payload_length, "CONNECT Payload")
        return cls.from_bytes(data, 0, len(data), variable_header)

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray,
        offset: int,
        end: int,
        variable_header: ConnectVariableHeader,
    ) -> Self:
        """Decode a MQTT 5.0 CONNECT payload from packet-body bytes."""
        payload = cls()

        # [MQTT-3.1.3-1] CONNECT payload fields must appear in this order.
        payload.client_id, offset = decode_string_from_bytes(data, offset, end, field_name="CONNECT Client Identifier")

        if variable_header.will_flag:
            # [MQTT-3.1.2-9] Will Properties, Will Topic, and Will Payload are present when Will Flag is 1.
            payload.will_properties, offset = Properties.from_bytes(
                data,
                offset,
                end,
                packet_name=PACKET_WILL,
                field_name="CONNECT",
            )
            payload.will_topic, offset = decode_string_from_bytes(data, offset, end, field_name="CONNECT Will Topic")
            payload.will_message, offset = decode_data_from_bytes(data, offset, end)

        if variable_header.username_flag:
            # [MQTT-3.1.2-17] User Name is present when the User Name Flag is 1.
            payload.username, offset = decode_string_from_bytes(data, offset, end, field_name="CONNECT User Name")

        if variable_header.password_flag:
            # [MQTT-3.1.2-19] Password is present when the Password Flag is 1.
            payload.password, offset = decode_data_from_bytes(data, offset, end)

        if offset != end:
            # [MQTT-3.1.2-10, MQTT-3.1.2-16, MQTT-3.1.2-18] Flag-cleared optional payload fields are absent.
            msg = "CONNECT payload contains fields not enabled by CONNECT flags"
            raise MQTTError(msg)

        return payload

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: ConnectVariableHeader | None = None,
    ) -> bytes | bytearray:
        """Encode the MQTT 5.0 CONNECT payload."""
        if variable_header is None:
            msg = "CONNECT variable header is required to encode payload"
            raise MQTTError(msg)
        if self.client_id is None:
            msg = "[MQTT-3.1.3-3] Client Identifier must be present"
            raise MQTTError(msg)

        out = bytearray()
        # [MQTT-3.1.3-3] Client Identifier is the first payload field.
        out.extend(encode_string(self.client_id))

        if variable_header.will_flag:
            if self.will_topic is None or self.will_message is None:
                msg = "[MQTT-3.1.2-9] Will Flag set, but Will Topic or Will Payload is missing"
                raise MQTTError(msg)
            out.extend(self.will_properties.encode())
            out.extend(encode_string(self.will_topic))
            out.extend(encode_data_with_length(self.will_message))

        if variable_header.username_flag:
            if self.username is None:
                msg = "[MQTT-3.1.2-17] User Name Flag set, but User Name is missing"
                raise MQTTError(msg)
            out.extend(encode_string(self.username))

        if variable_header.password_flag:
            if self.password is None:
                msg = "[MQTT-3.1.2-19] Password Flag set, but Password is missing"
                raise MQTTError(msg)
            out.extend(encode_data_with_length(self.password))

        return out


class ConnectPacket(MQTTPacket[ConnectVariableHeader, ConnectPayload, MQTTFixedHeader]):  # type: ignore[type-var]
    """MQTT 5.0 CONNECT packet (§3.1)."""

    VARIABLE_HEADER = ConnectVariableHeader
    PAYLOAD = ConnectPayload

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: ConnectVariableHeader | None = None,
        payload: ConnectPayload | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(CONNECT, 0x00)
        elif fixed.packet_type != CONNECT:
            msg = f"Invalid fixed packet type {fixed.packet_type} for ConnectPacket init"
            raise AMQTTError(msg) from None
        elif fixed.flags != 0x00:
            msg = "Invalid fixed header flags for MQTT 5.0 CONNECT"
            raise MQTTError(msg)
        else:
            header = fixed

        super().__init__(header, variable_header, payload)

    @classmethod
    def build(
        cls,
        client_id: str = "",
        *,
        clean_start: bool = False,
        keep_alive: int = 0,
        properties: Properties | None = None,
        will_topic: str | None = None,
        will_message: bytes | bytearray | None = None,
        will_qos: int = 0,
        will_retain: bool = False,
        will_properties: Properties | None = None,
        username: str | None = None,
        password: bytes | bytearray | None = None,
    ) -> Self:
        """Build an outgoing MQTT 5.0 CONNECT packet."""
        flags = 0
        if username is not None:
            flags |= ConnectVariableHeader.USERNAME_FLAG
        if password is not None:
            flags |= ConnectVariableHeader.PASSWORD_FLAG
        if clean_start:
            flags |= ConnectVariableHeader.CLEAN_START_FLAG

        has_will = will_topic is not None or will_message is not None or will_properties is not None
        if has_will:
            if will_topic is None or will_message is None:
                msg = "[MQTT-3.1.2-9] Will Topic and Will Payload are required when Will Properties are set"
                raise MQTTError(msg)
            flags |= ConnectVariableHeader.WILL_FLAG
            flags |= will_qos << 3
            if will_retain:
                flags |= ConnectVariableHeader.WILL_RETAIN_FLAG
        elif will_qos != 0 or will_retain:
            msg = "[MQTT-3.1.2-11, MQTT-3.1.2-13] Will QoS and Will Retain require Will Flag"
            raise MQTTError(msg)

        variable_header = ConnectVariableHeader(flags, keep_alive, properties=properties)
        payload = ConnectPayload(client_id, will_topic, will_message, username, password, will_properties)
        return cls(variable_header=variable_header, payload=payload)

    @classmethod
    async def from_stream(
        cls,
        reader: ReaderAdapter,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: ConnectVariableHeader | None = None,
    ) -> Self:
        """Decode a MQTT 5.0 CONNECT packet from a stream."""
        if fixed_header is None:
            try:
                fixed_header = await cls.FIXED_HEADER.from_stream(reader)
            except (CodecError, MQTTError, NoDataError, struct.error) as exc:
                msg = "Malformed MQTT 5.0 CONNECT fixed header"
                raise MQTTError(msg) from exc
        if fixed_header is None:
            msg = "No MQTT 5.0 CONNECT fixed header available"
            raise MQTTError(msg)
        if fixed_header.packet_type != CONNECT:
            msg = f"Invalid fixed packet type {fixed_header.packet_type} for ConnectPacket init"
            raise AMQTTError(msg) from None
        if fixed_header.flags != 0x00:
            msg = "Invalid fixed header flags for MQTT 5.0 CONNECT"
            raise MQTTError(msg)

        try:
            if variable_header is None:
                body = await read_exact(reader, fixed_header.remaining_length, "CONNECT packet body")
                variable_header, offset = cls.VARIABLE_HEADER.from_bytes(body, len(body))
                payload = cls.PAYLOAD.from_bytes(body, offset, len(body), variable_header)
            else:
                payload = await cls.PAYLOAD.from_stream(reader, fixed_header, variable_header)
        except (CodecError, MQTTError, NoDataError, struct.error) as exc:
            msg = "Malformed MQTT 5.0 CONNECT packet"
            raise MQTTError(msg) from exc

        return cls(fixed_header, variable_header, payload)

    @property
    def proto_name(self) -> str:
        """Return the CONNECT Protocol Name."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.proto_name

    @proto_name.setter
    def proto_name(self, name: str) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.proto_name = name

    @property
    def proto_level(self) -> int:
        """Return the CONNECT Protocol Level."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.proto_level

    @proto_level.setter
    def proto_level(self, level: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.proto_level = level

    @property
    def username_flag(self) -> bool:
        """Return whether the CONNECT User Name Flag is set."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.username_flag

    @username_flag.setter
    def username_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.username_flag = flag

    @property
    def password_flag(self) -> bool:
        """Return whether the CONNECT Password Flag is set."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.password_flag

    @password_flag.setter
    def password_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.password_flag = flag

    @property
    def clean_start_flag(self) -> bool:
        """Return the CONNECT Clean Start flag."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.clean_start_flag

    @clean_start_flag.setter
    def clean_start_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.clean_start_flag = flag

    @property
    def will_retain_flag(self) -> bool:
        """Return whether the CONNECT Will Retain flag is set."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.will_retain_flag

    @will_retain_flag.setter
    def will_retain_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.will_retain_flag = flag

    @property
    def will_qos(self) -> int:
        """Return the CONNECT Will QoS value."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.will_qos

    @will_qos.setter
    def will_qos(self, flag: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.will_qos = flag

    @property
    def will_flag(self) -> bool:
        """Return whether the CONNECT Will Flag is set."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.will_flag

    @will_flag.setter
    def will_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.will_flag = flag

    @property
    def reserved_flag(self) -> bool:
        """Return whether the CONNECT reserved flag bit is set."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.reserved_flag

    @reserved_flag.setter
    def reserved_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.reserved_flag = flag

    @property
    def keep_alive(self) -> int:
        """Return the CONNECT Keep Alive value."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.keep_alive

    @keep_alive.setter
    def keep_alive(self, keep_alive: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.keep_alive = keep_alive

    @property
    def properties(self) -> Properties:
        """Return the CONNECT properties."""
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.properties

    @property
    def client_id(self) -> str | None:
        """Return the CONNECT Client Identifier."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.client_id

    @client_id.setter
    def client_id(self, client_id: str) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.client_id = client_id

    @property
    def client_id_is_random(self) -> bool:
        """Return whether the Client Identifier was generated locally."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.client_id_is_random

    @client_id_is_random.setter
    def client_id_is_random(self, client_id_is_random: bool) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.client_id_is_random = client_id_is_random

    @property
    def will_topic(self) -> str | None:
        """Return the CONNECT Will Topic."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.will_topic

    @will_topic.setter
    def will_topic(self, will_topic: str) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.will_topic = will_topic

    @property
    def will_message(self) -> bytes | bytearray | None:
        """Return the CONNECT Will Payload."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.will_message

    @will_message.setter
    def will_message(self, will_message: bytes | bytearray) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.will_message = will_message

    @property
    def will_properties(self) -> Properties:
        """Return the CONNECT Will Properties."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.will_properties

    @property
    def username(self) -> str | None:
        """Return the CONNECT User Name."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.username

    @username.setter
    def username(self, username: str) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.username = username

    @property
    def password(self) -> bytes | bytearray | None:
        """Return the CONNECT Password binary data."""
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.password

    @password.setter
    def password(self, password: bytes | bytearray) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.password = password
