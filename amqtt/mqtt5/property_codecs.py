"""MQTT 5.0 Properties encoding and decoding (§2.2.2) helpers."""
from __future__ import annotations

from typing import Any, TypeAlias, TypeGuard

from amqtt.codecs_amqtt import (
    bytes_to_int,
    decode_string_from_bytes,
    decode_variable_byte_int,
    encode_data_with_length,
    encode_string,
    encode_variable_byte_int,
    int_to_bytes,
)
from amqtt.errors import MQTTError
from amqtt.mqtt5.property_ids import PacketName, PropertyDefinition, PropertyWireType

PropertyValue: TypeAlias = int | str | bytes | bytearray | tuple[str, str] | list[int] | list[tuple[str, str]]


def is_list_of_tuple_or_int(val: PropertyValue) -> TypeGuard[list[tuple[str, str] | int]]:
    """Check if a value is a list of tuples or ints."""
    return isinstance(val, list) and (all(isinstance(x, tuple) for x in val) or all(isinstance(x, int) for x in val))


def is_int_list(val: PropertyValue) -> TypeGuard[list[int]]:
    """Check if a value is a list of ints."""
    return isinstance(val, list) and all(isinstance(x, int) for x in val)


def is_tuple_list(val: PropertyValue) -> TypeGuard[list[tuple[str, str]]]:
    """Check if a value is a list of tuples."""
    return isinstance(val, list) and all(isinstance(x, tuple) for x in val)


def validate_packet_usage(definition: PropertyDefinition, packet_name: PacketName) -> None:
    """Validate that a property definition is correct for a given packet."""
    if packet_name in definition.packets:
        return
    msg = f"Property {definition.name} is not valid on {packet_name}"
    raise MQTTError(msg)


def validate_and_normalize_property_type(
    definition: PropertyDefinition,
    value: PropertyValue,
    packet_name: PacketName,
) -> PropertyValue:
    """Validate that properties for the packet are formed with correct types.

    For some property values, normalize into a list of values.
    """
    if definition.is_repeatable(packet_name):
        if definition.wire_type is PropertyWireType.UTF8_STRING_PAIR:
            if isinstance(value, tuple):
                validate_string_pair(definition, value)
                return [value]
            if isinstance(value, list):
                for item in value:
                    validate_string_pair(definition, item)
                return value
        elif definition.wire_type is PropertyWireType.VARIABLE_BYTE_INTEGER:
            if isinstance(value, int):
                validate_int(definition, value, 0, 268_435_455)
                validate_protocol_constraints(definition, value)
                return [value]
            if isinstance(value, list) and all(isinstance(item, int) for item in value):
                for item in value:
                    validate_int(definition, item, 0, 268_435_455)
                    validate_protocol_constraints(definition, item)
                return value
        msg = f"Invalid value for repeatable property {definition.name}: {value!r}"
        raise MQTTError(msg)

    validate_single_value(definition, value)
    return value


def validate_single_value(definition: PropertyDefinition, value: Any) -> None:
    """Validate that a single value is of the correct type for a property definition."""
    match definition.wire_type:
        case PropertyWireType.BYTE:
            validate_int(definition, value, 0, 0xFF)
        case PropertyWireType.TWO_BYTE_INTEGER:
            validate_int(definition, value, 0, 0xFFFF)
        case PropertyWireType.FOUR_BYTE_INTEGER:
            validate_int(definition, value, 0, 0xFFFF_FFFF)
        case PropertyWireType.VARIABLE_BYTE_INTEGER:
            validate_int(definition, value, 0, 268_435_455)
        case PropertyWireType.UTF8_STRING:
            if not isinstance(value, str):
                msg = f"Property {definition.name} requires a string value"
                raise MQTTError(msg)
        case PropertyWireType.UTF8_STRING_PAIR:
            validate_string_pair(definition, value)
        case PropertyWireType.BINARY_DATA:
            if not isinstance(value, (bytes, bytearray)):
                msg = f"Property {definition.name} requires bytes"
                raise MQTTError(msg)
    validate_protocol_constraints(definition, value)


def validate_int(definition: PropertyDefinition, value: Any, minimum: int, maximum: int) -> None:
    """Validate that a single value is of the correct type for a property definition."""
    if not isinstance(value, int) or value < minimum or value > maximum:
        msg = f"Property {definition.name} requires an integer from {minimum} to {maximum}"
        raise MQTTError(msg)


def validate_protocol_constraints(definition: PropertyDefinition, value: Any) -> None:
    """Validate that a single value is within the protocol constraints for a property definition."""
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


def validate_string_pair(definition: PropertyDefinition, value: Any) -> None:
    """Validate that a single value is a string pair for a property definition."""
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[0], str)
        or not isinstance(value[1], str)
    ):
        msg = f"Property {definition.name} requires a string pair"
        raise MQTTError(msg)


def encode_property(definition: PropertyDefinition, value: Any) -> bytes:
    """Encode a property value into a byte string."""
    out = bytearray(encode_variable_byte_int(definition.identifier))
    match definition.wire_type:
        case PropertyWireType.BYTE:
            validate_int(definition, value, 0, 0xFF)
            validate_protocol_constraints(definition, value)
            out.extend(int_to_bytes(value, 1))
        case PropertyWireType.TWO_BYTE_INTEGER:
            validate_int(definition, value, 0, 0xFFFF)
            validate_protocol_constraints(definition, value)
            out.extend(int_to_bytes(value, 2))
        case PropertyWireType.FOUR_BYTE_INTEGER:
            validate_int(definition, value, 0, 0xFFFF_FFFF)
            validate_protocol_constraints(definition, value)
            out.extend(int_to_bytes(value, 4))
        case PropertyWireType.VARIABLE_BYTE_INTEGER:
            validate_int(definition, value, 0, 268_435_455)
            validate_protocol_constraints(definition, value)
            out.extend(encode_variable_byte_int(value))
        case PropertyWireType.UTF8_STRING:
            if not isinstance(value, str):
                msg = f"Property {definition.name} requires a string value"
                raise MQTTError(msg)
            out.extend(encode_string(value))
        case PropertyWireType.UTF8_STRING_PAIR:
            validate_string_pair(definition, value)
            out.extend(encode_string(value[0]))
            out.extend(encode_string(value[1]))
        case PropertyWireType.BINARY_DATA:
            if not isinstance(value, (bytes, bytearray)):
                msg = f"Property {definition.name} requires bytes"
                raise MQTTError(msg)
            out.extend(encode_data_with_length(value))
    return bytes(out)


def decode_property(definition: PropertyDefinition, data: bytes | bytearray, offset: int, end: int) -> tuple[PropertyValue, int]:
    """Decode a property value from a byte string."""
    if offset > end:
        msg = f"Property {definition.name} exceeds properties length"
        raise MQTTError(msg)

    match definition.wire_type:
        case PropertyWireType.BYTE:
            require_available(definition, offset, end, 1)
            return data[offset], offset + 1
        case PropertyWireType.TWO_BYTE_INTEGER:
            require_available(definition, offset, end, 2)
            return bytes_to_int(bytes(data[offset:offset + 2])), offset + 2
        case PropertyWireType.FOUR_BYTE_INTEGER:
            require_available(definition, offset, end, 4)
            return bytes_to_int(bytes(data[offset:offset + 4])), offset + 4
        case PropertyWireType.VARIABLE_BYTE_INTEGER:
            return decode_variable_byte_int(data, offset)
        case PropertyWireType.UTF8_STRING:
            value, next_offset = decode_string_from_bytes(data, offset, end)
            return value, next_offset
        case PropertyWireType.UTF8_STRING_PAIR:
            key, next_offset = decode_string_from_bytes(data, offset, end)
            value, next_offset = decode_string_from_bytes(data, next_offset, end)
            return (key, value), next_offset
        case PropertyWireType.BINARY_DATA:
            binary_value, next_offset = decode_data_from_bytes(data, offset, end)
            return binary_value, next_offset


def require_available(definition: PropertyDefinition, offset: int, end: int, needed: int) -> None:
    """Validate that there is enough data available to decode a property value."""
    if offset + needed > end:
        msg = f"Property {definition.name} exceeds properties length"
        raise MQTTError(msg)


def decode_data_from_bytes(data: bytes | bytearray, offset: int, end: int) -> tuple[bytes, int]:
    """Decode a binary property value from a byte string."""
    if offset + 2 > end:
        msg = "Binary property length exceeds properties length"
        raise MQTTError(msg)
    length = bytes_to_int(bytes(data[offset:offset + 2]))
    offset += 2
    if offset + length > end:
        msg = "Binary property value exceeds properties length"
        raise MQTTError(msg)
    return bytes(data[offset:offset + length]), offset + length
