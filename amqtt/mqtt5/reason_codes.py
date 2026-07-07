"""MQTT 5.0 reason codes (§2.4)."""
from __future__ import annotations

from enum import IntEnum
from typing import Final


class ReasonCode(IntEnum):
    """MQTT 5.0 Reason Code values (§2.4, Table 2-6)."""

    SUCCESS = 0x00
    NORMAL_DISCONNECTION = 0x00
    GRANTED_QOS_0 = 0x00
    GRANTED_QOS_1 = 0x01
    GRANTED_QOS_2 = 0x02
    DISCONNECT_WITH_WILL_MESSAGE = 0x04
    NO_MATCHING_SUBSCRIBERS = 0x10
    NO_SUBSCRIPTION_EXISTED = 0x11
    CONTINUE_AUTHENTICATION = 0x18
    RE_AUTHENTICATE = 0x19
    UNSPECIFIED_ERROR = 0x80
    MALFORMED_PACKET = 0x81
    PROTOCOL_ERROR = 0x82
    IMPLEMENTATION_SPECIFIC_ERROR = 0x83
    UNSUPPORTED_PROTOCOL_VERSION = 0x84
    CLIENT_IDENTIFIER_NOT_VALID = 0x85
    BAD_USER_NAME_OR_PASSWORD = 0x86
    NOT_AUTHORIZED = 0x87
    SERVER_UNAVAILABLE = 0x88
    SERVER_BUSY = 0x89
    BANNED = 0x8A
    SERVER_SHUTTING_DOWN = 0x8B
    BAD_AUTHENTICATION_METHOD = 0x8C
    KEEP_ALIVE_TIMEOUT = 0x8D
    SESSION_TAKEN_OVER = 0x8E
    TOPIC_FILTER_INVALID = 0x8F
    TOPIC_NAME_INVALID = 0x90
    PACKET_IDENTIFIER_IN_USE = 0x91
    PACKET_IDENTIFIER_NOT_FOUND = 0x92
    RECEIVE_MAXIMUM_EXCEEDED = 0x93
    TOPIC_ALIAS_INVALID = 0x94
    PACKET_TOO_LARGE = 0x95
    MESSAGE_RATE_TOO_HIGH = 0x96
    QUOTA_EXCEEDED = 0x97
    ADMINISTRATIVE_ACTION = 0x98
    PAYLOAD_FORMAT_INVALID = 0x99
    RETAIN_NOT_SUPPORTED = 0x9A
    QOS_NOT_SUPPORTED = 0x9B
    USE_ANOTHER_SERVER = 0x9C
    SERVER_MOVED = 0x9D
    SHARED_SUBSCRIPTIONS_NOT_SUPPORTED = 0x9E
    CONNECTION_RATE_EXCEEDED = 0x9F
    MAXIMUM_CONNECT_TIME = 0xA0
    SUBSCRIPTION_IDENTIFIERS_NOT_SUPPORTED = 0xA1
    WILDCARD_SUBSCRIPTIONS_NOT_SUPPORTED = 0xA2

    def is_error(self) -> bool:
        """Return whether this reason code represents an error."""
        return self >= 0x80

    @property
    def description(self) -> str:
        """Return a human-readable reason-code description."""
        return _DESCRIPTIONS[int(self)]


_DESCRIPTIONS: Final[dict[int, str]] = {
    0x00: "Success",
    0x01: "Granted QoS 1",
    0x02: "Granted QoS 2",
    0x04: "Disconnect with Will Message",
    0x10: "No matching subscribers",
    0x11: "No subscription existed",
    0x18: "Continue authentication",
    0x19: "Re-authenticate",
    0x80: "Unspecified error",
    0x81: "Malformed Packet",
    0x82: "Protocol Error",
    0x83: "Implementation specific error",
    0x84: "Unsupported Protocol Version",
    0x85: "Client Identifier not valid",
    0x86: "Bad User Name or Password",
    0x87: "Not authorized",
    0x88: "Server unavailable",
    0x89: "Server busy",
    0x8A: "Banned",
    0x8B: "Server shutting down",
    0x8C: "Bad authentication method",
    0x8D: "Keep Alive timeout",
    0x8E: "Session taken over",
    0x8F: "Topic Filter invalid",
    0x90: "Topic Name invalid",
    0x91: "Packet Identifier in use",
    0x92: "Packet Identifier not found",
    0x93: "Receive Maximum exceeded",
    0x94: "Topic Alias invalid",
    0x95: "Packet too large",
    0x96: "Message rate too high",
    0x97: "Quota exceeded",
    0x98: "Administrative action",
    0x99: "Payload format invalid",
    0x9A: "Retain not supported",
    0x9B: "QoS not supported",
    0x9C: "Use another server",
    0x9D: "Server moved",
    0x9E: "Shared Subscriptions not supported",
    0x9F: "Connection rate exceeded",
    0xA0: "Maximum connect time",
    0xA1: "Subscription Identifiers not supported",
    0xA2: "Wildcard Subscriptions not supported",
}
