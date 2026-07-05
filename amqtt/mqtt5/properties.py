"""MQTT 5.0 Properties encoding and decoding (§2.2.2)."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing_extensions import Self

from amqtt.codecs_amqtt import (
    decode_variable_byte_int,
    decode_variable_byte_int_from_stream,
    encode_variable_byte_int,
    read_or_raise,
)
from amqtt.errors import MQTTError
from amqtt.mqtt5.property_codecs import (
    PropertyValue,
    decode_property,
    encode_property,
    is_list_of_tuple_or_int,
    validate_and_normalize_property_type,
    validate_packet_usage,
)
from amqtt.mqtt5.property_ids import PacketName, get_definition

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from amqtt.adapters import ReaderAdapter


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
        definition = get_definition(identifier)
        validate_packet_usage(definition, self._packet_name)
        normalized = validate_and_normalize_property_type(definition, value, self._packet_name)

        if definition.is_repeatable(self._packet_name):
            existing = self._values.get(identifier)
            if existing is None:
                self._values[identifier] = normalized
                return
            if not is_list_of_tuple_or_int(existing) or not is_list_of_tuple_or_int(normalized):
                msg = f"Repeatable property {definition.name} must be stored as a list of ints"
                raise MQTTError(msg)
            existing.extend(normalized)
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
            definition = get_definition(identifier)
            validate_packet_usage(definition, self._packet_name)
            if definition.is_repeatable(self._packet_name):
                if not isinstance(value, list):
                    msg = f"Repeatable property {definition.name} must be stored as a list"
                    raise MQTTError(msg)
                for item in value:
                    payload.extend(encode_property(definition, item))
            else:
                payload.extend(encode_property(definition, value))
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
            definition = get_definition(identifier)
            validate_packet_usage(definition, packet_name)
            value, offset = decode_property(definition, data, offset, end)
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
