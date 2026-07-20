"""MQTT 5.0 property identifiers and wire metadata."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from amqtt.errors import MQTTError

PacketName: TypeAlias = str

# Packets in mqtt5 that allow for the property field (all except PING)

PACKET_CONNECT = "CONNECT"
PACKET_CONNACK = "CONNACK"
PACKET_PUBLISH = "PUBLISH"
PACKET_PUBACK = "PUBACK"
PACKET_PUBREC = "PUBREC"
PACKET_PUBREL = "PUBREL"
PACKET_PUBCOMP = "PUBCOMP"
PACKET_SUBSCRIBE = "SUBSCRIBE"
PACKET_SUBACK = "SUBACK"
PACKET_UNSUBSCRIBE = "UNSUBSCRIBE"
PACKET_UNSUBACK = "UNSUBACK"
PACKET_DISCONNECT = "DISCONNECT"
PACKET_AUTH = "AUTH"
PACKET_WILL = "WILL"


class PropertyWireType(Enum):
    """MQTT 5.0 property value wire types."""

    BYTE = "byte"
    TWO_BYTE_INTEGER = "two_byte_integer"
    FOUR_BYTE_INTEGER = "four_byte_integer"
    VARIABLE_BYTE_INTEGER = "variable_byte_integer"
    UTF8_STRING = "utf8_string"
    UTF8_STRING_PAIR = "utf8_string_pair"
    BINARY_DATA = "binary_data"


@dataclass(frozen=True)
class PropertyDefinition:
    """Metadata for an MQTT 5.0 property identifier."""

    identifier: int
    name: str
    wire_type: PropertyWireType
    packets: frozenset[PacketName]
    repeatable_packets: frozenset[PacketName] = frozenset()
    minimum: int | None = None
    maximum: int | None = None
    allowed_values: frozenset[int] | None = None

    def is_repeatable(self, packet_name: PacketName) -> bool:
        """Return whether the property can appear more than once."""
        return packet_name in self.repeatable_packets


PAYLOAD_FORMAT_INDICATOR = 0x01
MESSAGE_EXPIRY_INTERVAL = 0x02
CONTENT_TYPE = 0x03
RESPONSE_TOPIC = 0x08
CORRELATION_DATA = 0x09
SUBSCRIPTION_IDENTIFIER = 0x0B
SESSION_EXPIRY_INTERVAL = 0x11
ASSIGNED_CLIENT_IDENTIFIER = 0x12
SERVER_KEEP_ALIVE = 0x13
AUTHENTICATION_METHOD = 0x15
AUTHENTICATION_DATA = 0x16
REQUEST_PROBLEM_INFORMATION = 0x17
WILL_DELAY_INTERVAL = 0x18
REQUEST_RESPONSE_INFORMATION = 0x19
RESPONSE_INFORMATION = 0x1A
SERVER_REFERENCE = 0x1C
REASON_STRING = 0x1F
RECEIVE_MAXIMUM = 0x21
TOPIC_ALIAS_MAXIMUM = 0x22
TOPIC_ALIAS = 0x23
MAXIMUM_QOS = 0x24
RETAIN_AVAILABLE = 0x25
USER_PROPERTY = 0x26
MAXIMUM_PACKET_SIZE = 0x27
WILDCARD_SUBSCRIPTION_AVAILABLE = 0x28
SUBSCRIPTION_IDENTIFIER_AVAILABLE = 0x29
SHARED_SUBSCRIPTION_AVAILABLE = 0x2A

# properties differ by message type, map to define each:

PROPERTY_DEFINITIONS: dict[int, PropertyDefinition] = {
    PAYLOAD_FORMAT_INDICATOR: PropertyDefinition(
        PAYLOAD_FORMAT_INDICATOR,
        "Payload Format Indicator",
        PropertyWireType.BYTE,
        frozenset({PACKET_PUBLISH, PACKET_WILL}),
        allowed_values=frozenset({0, 1}),
    ),
    MESSAGE_EXPIRY_INTERVAL: PropertyDefinition(
        MESSAGE_EXPIRY_INTERVAL,
        "Message Expiry Interval",
        PropertyWireType.FOUR_BYTE_INTEGER,
        frozenset({PACKET_PUBLISH, PACKET_WILL}),
    ),
    CONTENT_TYPE: PropertyDefinition(
        CONTENT_TYPE,
        "Content Type",
        PropertyWireType.UTF8_STRING,
        frozenset({PACKET_PUBLISH, PACKET_WILL}),
    ),
    RESPONSE_TOPIC: PropertyDefinition(
        RESPONSE_TOPIC,
        "Response Topic",
        PropertyWireType.UTF8_STRING,
        frozenset({PACKET_PUBLISH, PACKET_WILL}),
    ),
    CORRELATION_DATA: PropertyDefinition(
        CORRELATION_DATA,
        "Correlation Data",
        PropertyWireType.BINARY_DATA,
        frozenset({PACKET_PUBLISH, PACKET_WILL}),
    ),
    SUBSCRIPTION_IDENTIFIER: PropertyDefinition(
        SUBSCRIPTION_IDENTIFIER,
        "Subscription Identifier",
        PropertyWireType.VARIABLE_BYTE_INTEGER,
        frozenset({PACKET_PUBLISH, PACKET_SUBSCRIBE}),
        repeatable_packets=frozenset({PACKET_PUBLISH}),
        minimum=1,
        maximum=268_435_455,
    ),
    SESSION_EXPIRY_INTERVAL: PropertyDefinition(
        SESSION_EXPIRY_INTERVAL,
        "Session Expiry Interval",
        PropertyWireType.FOUR_BYTE_INTEGER,
        frozenset({PACKET_CONNECT, PACKET_CONNACK, PACKET_DISCONNECT}),
    ),
    ASSIGNED_CLIENT_IDENTIFIER: PropertyDefinition(
        ASSIGNED_CLIENT_IDENTIFIER,
        "Assigned Client Identifier",
        PropertyWireType.UTF8_STRING,
        frozenset({PACKET_CONNACK}),
    ),
    SERVER_KEEP_ALIVE: PropertyDefinition(
        SERVER_KEEP_ALIVE,
        "Server Keep Alive",
        PropertyWireType.TWO_BYTE_INTEGER,
        frozenset({PACKET_CONNACK}),
    ),
    AUTHENTICATION_METHOD: PropertyDefinition(
        AUTHENTICATION_METHOD,
        "Authentication Method",
        PropertyWireType.UTF8_STRING,
        frozenset({PACKET_CONNECT, PACKET_CONNACK, PACKET_AUTH}),
    ),
    AUTHENTICATION_DATA: PropertyDefinition(
        AUTHENTICATION_DATA,
        "Authentication Data",
        PropertyWireType.BINARY_DATA,
        frozenset({PACKET_CONNECT, PACKET_CONNACK, PACKET_AUTH}),
    ),
    REQUEST_PROBLEM_INFORMATION: PropertyDefinition(
        REQUEST_PROBLEM_INFORMATION,
        "Request Problem Information",
        PropertyWireType.BYTE,
        frozenset({PACKET_CONNECT}),
        allowed_values=frozenset({0, 1}),
    ),
    WILL_DELAY_INTERVAL: PropertyDefinition(
        WILL_DELAY_INTERVAL,
        "Will Delay Interval",
        PropertyWireType.FOUR_BYTE_INTEGER,
        frozenset({PACKET_WILL}),
    ),
    REQUEST_RESPONSE_INFORMATION: PropertyDefinition(
        REQUEST_RESPONSE_INFORMATION,
        "Request Response Information",
        PropertyWireType.BYTE,
        frozenset({PACKET_CONNECT}),
        allowed_values=frozenset({0, 1}),
    ),
    RESPONSE_INFORMATION: PropertyDefinition(
        RESPONSE_INFORMATION,
        "Response Information",
        PropertyWireType.UTF8_STRING,
        frozenset({PACKET_CONNACK}),
    ),
    SERVER_REFERENCE: PropertyDefinition(
        SERVER_REFERENCE,
        "Server Reference",
        PropertyWireType.UTF8_STRING,
        frozenset({PACKET_CONNACK, PACKET_DISCONNECT}),
    ),
    REASON_STRING: PropertyDefinition(
        REASON_STRING,
        "Reason String",
        PropertyWireType.UTF8_STRING,
        frozenset({
            PACKET_CONNACK,
            PACKET_PUBACK,
            PACKET_PUBREC,
            PACKET_PUBREL,
            PACKET_PUBCOMP,
            PACKET_SUBACK,
            PACKET_UNSUBACK,
            PACKET_DISCONNECT,
            PACKET_AUTH,
        }),
    ),
    RECEIVE_MAXIMUM: PropertyDefinition(
        RECEIVE_MAXIMUM,
        "Receive Maximum",
        PropertyWireType.TWO_BYTE_INTEGER,
        frozenset({PACKET_CONNECT, PACKET_CONNACK}),
        minimum=1,
    ),
    TOPIC_ALIAS_MAXIMUM: PropertyDefinition(
        TOPIC_ALIAS_MAXIMUM,
        "Topic Alias Maximum",
        PropertyWireType.TWO_BYTE_INTEGER,
        frozenset({PACKET_CONNECT, PACKET_CONNACK}),
    ),
    TOPIC_ALIAS: PropertyDefinition(
        TOPIC_ALIAS,
        "Topic Alias",
        PropertyWireType.TWO_BYTE_INTEGER,
        frozenset({PACKET_PUBLISH}),
        minimum=1,
    ),
    MAXIMUM_QOS: PropertyDefinition(
        MAXIMUM_QOS,
        "Maximum QoS",
        PropertyWireType.BYTE,
        frozenset({PACKET_CONNACK}),
        allowed_values=frozenset({0, 1}),
    ),
    RETAIN_AVAILABLE: PropertyDefinition(
        RETAIN_AVAILABLE,
        "Retain Available",
        PropertyWireType.BYTE,
        frozenset({PACKET_CONNACK}),
        allowed_values=frozenset({0, 1}),
    ),
    USER_PROPERTY: PropertyDefinition(
        USER_PROPERTY,
        "User Property",
        PropertyWireType.UTF8_STRING_PAIR,
        frozenset({
            PACKET_CONNECT,
            PACKET_CONNACK,
            PACKET_PUBLISH,
            PACKET_PUBACK,
            PACKET_PUBREC,
            PACKET_PUBREL,
            PACKET_PUBCOMP,
            PACKET_SUBSCRIBE,
            PACKET_SUBACK,
            PACKET_UNSUBSCRIBE,
            PACKET_UNSUBACK,
            PACKET_DISCONNECT,
            PACKET_AUTH,
            PACKET_WILL,
        }),
        repeatable_packets=frozenset({
            PACKET_CONNECT,
            PACKET_CONNACK,
            PACKET_PUBLISH,
            PACKET_PUBACK,
            PACKET_PUBREC,
            PACKET_PUBREL,
            PACKET_PUBCOMP,
            PACKET_SUBSCRIBE,
            PACKET_SUBACK,
            PACKET_UNSUBSCRIBE,
            PACKET_UNSUBACK,
            PACKET_DISCONNECT,
            PACKET_AUTH,
            PACKET_WILL,
        }),
    ),
    MAXIMUM_PACKET_SIZE: PropertyDefinition(
        MAXIMUM_PACKET_SIZE,
        "Maximum Packet Size",
        PropertyWireType.FOUR_BYTE_INTEGER,
        frozenset({PACKET_CONNECT, PACKET_CONNACK}),
        minimum=1,
    ),
    WILDCARD_SUBSCRIPTION_AVAILABLE: PropertyDefinition(
        WILDCARD_SUBSCRIPTION_AVAILABLE,
        "Wildcard Subscription Available",
        PropertyWireType.BYTE,
        frozenset({PACKET_CONNACK}),
        allowed_values=frozenset({0, 1}),
    ),
    SUBSCRIPTION_IDENTIFIER_AVAILABLE: PropertyDefinition(
        SUBSCRIPTION_IDENTIFIER_AVAILABLE,
        "Subscription Identifier Available",
        PropertyWireType.BYTE,
        frozenset({PACKET_CONNACK}),
        allowed_values=frozenset({0, 1}),
    ),
    SHARED_SUBSCRIPTION_AVAILABLE: PropertyDefinition(
        SHARED_SUBSCRIPTION_AVAILABLE,
        "Shared Subscription Available",
        PropertyWireType.BYTE,
        frozenset({PACKET_CONNACK}),
        allowed_values=frozenset({0, 1}),
    ),
}


def get_definition(identifier: int) -> PropertyDefinition:
    """Return the `PropertyDefinition` for a given identifier (after checking it exists)."""
    if identifier not in PROPERTY_DEFINITIONS:
        msg = f"Unknown MQTT 5.0 property identifier: {identifier:#x}"
        raise MQTTError(msg)
    return PROPERTY_DEFINITIONS[identifier]
