"""MQTT 5.0 Properties encoding and decoding (§2.2.2)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias, cast
from typing_extensions import Self

from amqtt.codecs_amqtt import (
    bytes_to_int,
    decode_variable_byte_int,
    decode_variable_byte_int_from_stream,
    encode_data_with_length,
    encode_string,
    encode_variable_byte_int,
    int_to_bytes,
    read_or_raise,
)
from amqtt.errors import MQTTError
from amqtt.mqtt5.property_ids import PROPERTY_DEFINITIONS, PacketName, PropertyDefinition, PropertyWireType

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from amqtt.adapters import ReaderAdapter

PropertyValue: TypeAlias = int | str | bytes | bytearray | tuple[str, str] | list[int] | list[tuple[str, str]]


class Properties:
    """Container for MQTT 5.0 packet properties.

    Properties are keyed by MQTT property identifier. Duplicate non-repeatable
    properties raise `MQTTError`; repeatable properties preserve insertion order.
    """

    def __init__(self, values: dict[int, PropertyValue] | None = None, *, packet_name: PacketName | None = None) -> None:
        self._packet_name = packet_name
        self._values: dict[int, PropertyValue] = {}
        if values:
            for identifier, value in values.items():
                self.set(identifier, value)

    def set(self, identifier: int, value: PropertyValue) -> None:
        """Set a property value.

        Args:
            identifier: MQTT 5.0 property identifier.
            value: Property value using the Python type for its wire type.

        Raises:
            MQTTError: If the identifier is unknown, the value has the wrong
                type, or a duplicate non-repeatable property is added.

        """
        definition = _definition(identifier)
        _validate_packet_usage(definition, self._packet_name)
        normalized = _normalize_value(definition, value, self._packet_name)

        if definition.is_repeatable(self._packet_name):
            existing = self._values.get(identifier)
            if existing is None:
                self._values[identifier] = normalized
                return
            if not isinstance(existing, list) or not isinstance(normalized, list):
                msg = f"Repeatable property {definition.name} must be stored as a list"
                raise MQTTError(msg)
            cast("list[Any]", existing).extend(cast("list[Any]", normalized))
            return

        if identifier in self._values:
            msg = f"Duplicate MQTT 5.0 property: {definition.name}"
            raise MQTTError(msg)
        self._values[identifier] = normalized

    def get(self, identifier: int, default: PropertyValue | None = None) -> PropertyValue | None:
        """Return a property value by identifier.

        Args:
            identifier: MQTT 5.0 property identifier.
            default: Value returned when the property is not present.

        Returns:
            The stored property value or `default`.

        """
        return self._values.get(identifier, default)

    def has(self, identifier: int) -> bool:
        """Return whether a property identifier is present."""
        return identifier in self._values

    def encode(self) -> bytes:
        r"""Encode properties with the MQTT 5.0 length prefix.

        Returns:
            MQTT 5.0 Properties bytes. Empty properties encode as `b"\\x00"`.

        """
        payload = bytearray()
        for identifier, value in self._values.items():
            definition = _definition(identifier)
            _validate_packet_usage(definition, self._packet_name)
            if definition.is_repeatable(self._packet_name):
                if not isinstance(value, list):
                    msg = f"Repeatable property {definition.name} must be stored as a list"
                    raise MQTTError(msg)
                for item in value:
                    payload.extend(_encode_property(definition, item))
            else:
                payload.extend(_encode_property(definition, value))
        return encode_variable_byte_int(len(payload)) + bytes(payload)

    @classmethod
    def decode(cls: type[Self], data: bytes | bytearray, *, packet_name: PacketName | None = None) -> Self:
        """Decode MQTT 5.0 Properties from bytes.

        Args:
            data: MQTT 5.0 Properties bytes including the length prefix.
            packet_name: Optional MQTT packet name used to validate whether
                properties are allowed and repeatable in that packet.

        Returns:
            Decoded `Properties`.

        Raises:
            MQTTError: If the property section is malformed.

        """
        property_length, offset = decode_variable_byte_int(data)
        end = offset + property_length
        if end > len(data):
            msg = "Properties length exceeds available bytes"
            raise MQTTError(msg)
        if end != len(data):
            msg = "Properties bytes contain trailing data"
            raise MQTTError(msg)

        properties = cls(packet_name=packet_name)
        while offset < end:
            identifier, offset = decode_variable_byte_int(data, offset)
            definition = _definition(identifier)
            _validate_packet_usage(definition, packet_name)
            value, offset = _decode_property(definition, data, offset, end)
            properties.set(identifier, value)
        return properties

    @classmethod
    async def from_stream(cls: type[Self], reader: ReaderAdapter, *, packet_name: PacketName | None = None) -> Self:
        """Read and decode MQTT 5.0 Properties from a stream."""
        property_length = await decode_variable_byte_int_from_stream(reader)
        data = await read_or_raise(reader, property_length)
        if len(data) != property_length:
            msg = "Properties length exceeds available stream bytes"
            raise MQTTError(msg)
        return cls.decode(encode_variable_byte_int(property_length) + data, packet_name=packet_name)

    def items(self) -> Iterable[tuple[int, PropertyValue]]:
        """Return stored property identifier/value pairs."""
        return self._values.items()

    def __iter__(self) -> Iterator[int]:
        """Return an iterator over stored property identifiers."""
        return iter(self._values)

    def __eq__(self, other: object) -> bool:
        """Compare properties by stored identifier/value pairs."""
        if not isinstance(other, Properties):
            return False
        return self._values == other._values

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"{self.__class__.__name__}({self._values!r})"


def _definition(identifier: int) -> PropertyDefinition:
    try:
        return PROPERTY_DEFINITIONS[identifier]
    except KeyError as exc:
        msg = f"Unknown MQTT 5.0 property identifier: {identifier:#x}"
        raise MQTTError(msg) from exc


def _validate_packet_usage(definition: PropertyDefinition, packet_name: PacketName | None) -> None:
    if packet_name is None or packet_name in definition.packets:
        return
    msg = f"Property {definition.name} is not valid on {packet_name}"
    raise MQTTError(msg)


def _normalize_value(
    definition: PropertyDefinition,
    value: PropertyValue,
    packet_name: PacketName | None,
) -> PropertyValue:
    if definition.is_repeatable(packet_name):
        if definition.wire_type is PropertyWireType.UTF8_STRING_PAIR:
            if isinstance(value, tuple):
                _validate_string_pair(definition, value)
                return [value]
            if isinstance(value, list):
                for item in value:
                    _validate_string_pair(definition, item)
                return value
        elif definition.wire_type is PropertyWireType.VARIABLE_BYTE_INTEGER:
            if isinstance(value, int):
                _validate_int(definition, value, 0, 268_435_455)
                _validate_protocol_constraints(definition, value)
                return [value]
            if isinstance(value, list) and all(isinstance(item, int) for item in value):
                for item in value:
                    _validate_int(definition, item, 0, 268_435_455)
                    _validate_protocol_constraints(definition, item)
                return value
        msg = f"Invalid value for repeatable property {definition.name}: {value!r}"
        raise MQTTError(msg)

    _validate_single_value(definition, value)
    return value


def _validate_single_value(definition: PropertyDefinition, value: Any) -> None:
    match definition.wire_type:
        case PropertyWireType.BYTE:
            _validate_int(definition, value, 0, 0xFF)
        case PropertyWireType.TWO_BYTE_INTEGER:
            _validate_int(definition, value, 0, 0xFFFF)
        case PropertyWireType.FOUR_BYTE_INTEGER:
            _validate_int(definition, value, 0, 0xFFFF_FFFF)
        case PropertyWireType.VARIABLE_BYTE_INTEGER:
            _validate_int(definition, value, 0, 268_435_455)
        case PropertyWireType.UTF8_STRING:
            if not isinstance(value, str):
                msg = f"Property {definition.name} requires a string value"
                raise MQTTError(msg)
        case PropertyWireType.UTF8_STRING_PAIR:
            _validate_string_pair(definition, value)
        case PropertyWireType.BINARY_DATA:
            if not isinstance(value, (bytes, bytearray)):
                msg = f"Property {definition.name} requires bytes"
                raise MQTTError(msg)
    _validate_protocol_constraints(definition, value)


def _validate_int(definition: PropertyDefinition, value: Any, minimum: int, maximum: int) -> None:
    if not isinstance(value, int) or value < minimum or value > maximum:
        msg = f"Property {definition.name} requires an integer from {minimum} to {maximum}"
        raise MQTTError(msg)


def _validate_protocol_constraints(definition: PropertyDefinition, value: Any) -> None:
    if not isinstance(value, int):
        return
    if definition.allowed_values is not None and value not in definition.allowed_values:
        msg = f"Property {definition.name} requires one of {sorted(definition.allowed_values)}"
        raise MQTTError(msg)
    if definition.minimum is not None and value < definition.minimum:
        msg = f"Property {definition.name} requires an integer >= {definition.minimum}"
        raise MQTTError(msg)
    if definition.maximum is not None and value > definition.maximum:
        msg = f"Property {definition.name} requires an integer <= {definition.maximum}"
        raise MQTTError(msg)


def _validate_string_pair(definition: PropertyDefinition, value: Any) -> None:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[0], str)
        or not isinstance(value[1], str)
    ):
        msg = f"Property {definition.name} requires a string pair"
        raise MQTTError(msg)


def _encode_property(definition: PropertyDefinition, value: Any) -> bytes:
    out = bytearray(encode_variable_byte_int(definition.identifier))
    match definition.wire_type:
        case PropertyWireType.BYTE:
            _validate_int(definition, value, 0, 0xFF)
            _validate_protocol_constraints(definition, value)
            out.extend(int_to_bytes(value, 1))
        case PropertyWireType.TWO_BYTE_INTEGER:
            _validate_int(definition, value, 0, 0xFFFF)
            _validate_protocol_constraints(definition, value)
            out.extend(int_to_bytes(value, 2))
        case PropertyWireType.FOUR_BYTE_INTEGER:
            _validate_int(definition, value, 0, 0xFFFF_FFFF)
            _validate_protocol_constraints(definition, value)
            out.extend(int_to_bytes(value, 4))
        case PropertyWireType.VARIABLE_BYTE_INTEGER:
            _validate_int(definition, value, 0, 268_435_455)
            _validate_protocol_constraints(definition, value)
            out.extend(encode_variable_byte_int(value))
        case PropertyWireType.UTF8_STRING:
            if not isinstance(value, str):
                msg = f"Property {definition.name} requires a string value"
                raise MQTTError(msg)
            out.extend(encode_string(value))
        case PropertyWireType.UTF8_STRING_PAIR:
            _validate_string_pair(definition, value)
            out.extend(encode_string(value[0]))
            out.extend(encode_string(value[1]))
        case PropertyWireType.BINARY_DATA:
            if not isinstance(value, (bytes, bytearray)):
                msg = f"Property {definition.name} requires bytes"
                raise MQTTError(msg)
            out.extend(encode_data_with_length(value))
    return bytes(out)


def _decode_property(definition: PropertyDefinition, data: bytes | bytearray, offset: int, end: int) -> tuple[PropertyValue, int]:
    if offset > end:
        msg = f"Property {definition.name} exceeds properties length"
        raise MQTTError(msg)

    match definition.wire_type:
        case PropertyWireType.BYTE:
            _require_available(definition, offset, end, 1)
            return data[offset], offset + 1
        case PropertyWireType.TWO_BYTE_INTEGER:
            _require_available(definition, offset, end, 2)
            return bytes_to_int(bytes(data[offset:offset + 2])), offset + 2
        case PropertyWireType.FOUR_BYTE_INTEGER:
            _require_available(definition, offset, end, 4)
            return bytes_to_int(bytes(data[offset:offset + 4])), offset + 4
        case PropertyWireType.VARIABLE_BYTE_INTEGER:
            return decode_variable_byte_int(data, offset)
        case PropertyWireType.UTF8_STRING:
            value, next_offset = _decode_string_from_bytes(data, offset, end)
            return value, next_offset
        case PropertyWireType.UTF8_STRING_PAIR:
            key, next_offset = _decode_string_from_bytes(data, offset, end)
            value, next_offset = _decode_string_from_bytes(data, next_offset, end)
            return (key, value), next_offset
        case PropertyWireType.BINARY_DATA:
            binary_value, next_offset = _decode_data_from_bytes(data, offset, end)
            return binary_value, next_offset


def _require_available(definition: PropertyDefinition, offset: int, end: int, needed: int) -> None:
    if offset + needed > end:
        msg = f"Property {definition.name} exceeds properties length"
        raise MQTTError(msg)


def _decode_string_from_bytes(data: bytes | bytearray, offset: int, end: int) -> tuple[str, int]:
    if offset + 2 > end:
        msg = "String property length exceeds properties length"
        raise MQTTError(msg)
    length = bytes_to_int(bytes(data[offset:offset + 2]))
    offset += 2
    if offset + length > end:
        msg = "String property value exceeds properties length"
        raise MQTTError(msg)
    try:
        return bytes(data[offset:offset + length]).decode("utf-8"), offset + length
    except UnicodeDecodeError as exc:
        msg = "String property value is not valid UTF-8"
        raise MQTTError(msg) from exc


def _decode_data_from_bytes(data: bytes | bytearray, offset: int, end: int) -> tuple[bytes, int]:
    if offset + 2 > end:
        msg = "Binary property length exceeds properties length"
        raise MQTTError(msg)
    length = bytes_to_int(bytes(data[offset:offset + 2]))
    offset += 2
    if offset + length > end:
        msg = "Binary property value exceeds properties length"
        raise MQTTError(msg)
    return bytes(data[offset:offset + length]), offset + length
