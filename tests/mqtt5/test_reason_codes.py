import pytest

from amqtt.mqtt3.connack import (
    BAD_USERNAME_PASSWORD,
    CONNECTION_ACCEPTED,
    IDENTIFIER_REJECTED,
    NOT_AUTHORIZED,
    SERVER_UNAVAILABLE,
    UNACCEPTABLE_PROTOCOL_VERSION,
)
from amqtt.mqtt5.reason_codes import ReasonCode


TABLE_2_6_REASON_CODES = {
    "SUCCESS": 0x00,
    "NORMAL_DISCONNECTION": 0x00,
    "GRANTED_QOS_0": 0x00,
    "GRANTED_QOS_1": 0x01,
    "GRANTED_QOS_2": 0x02,
    "DISCONNECT_WITH_WILL_MESSAGE": 0x04,
    "NO_MATCHING_SUBSCRIBERS": 0x10,
    "NO_SUBSCRIPTION_EXISTED": 0x11,
    "CONTINUE_AUTHENTICATION": 0x18,
    "RE_AUTHENTICATE": 0x19,
    "UNSPECIFIED_ERROR": 0x80,
    "MALFORMED_PACKET": 0x81,
    "PROTOCOL_ERROR": 0x82,
    "IMPLEMENTATION_SPECIFIC_ERROR": 0x83,
    "UNSUPPORTED_PROTOCOL_VERSION": 0x84,
    "CLIENT_IDENTIFIER_NOT_VALID": 0x85,
    "BAD_USER_NAME_OR_PASSWORD": 0x86,
    "NOT_AUTHORIZED": 0x87,
    "SERVER_UNAVAILABLE": 0x88,
    "SERVER_BUSY": 0x89,
    "BANNED": 0x8A,
    "SERVER_SHUTTING_DOWN": 0x8B,
    "BAD_AUTHENTICATION_METHOD": 0x8C,
    "KEEP_ALIVE_TIMEOUT": 0x8D,
    "SESSION_TAKEN_OVER": 0x8E,
    "TOPIC_FILTER_INVALID": 0x8F,
    "TOPIC_NAME_INVALID": 0x90,
    "PACKET_IDENTIFIER_IN_USE": 0x91,
    "PACKET_IDENTIFIER_NOT_FOUND": 0x92,
    "RECEIVE_MAXIMUM_EXCEEDED": 0x93,
    "TOPIC_ALIAS_INVALID": 0x94,
    "PACKET_TOO_LARGE": 0x95,
    "MESSAGE_RATE_TOO_HIGH": 0x96,
    "QUOTA_EXCEEDED": 0x97,
    "ADMINISTRATIVE_ACTION": 0x98,
    "PAYLOAD_FORMAT_INVALID": 0x99,
    "RETAIN_NOT_SUPPORTED": 0x9A,
    "QOS_NOT_SUPPORTED": 0x9B,
    "USE_ANOTHER_SERVER": 0x9C,
    "SERVER_MOVED": 0x9D,
    "SHARED_SUBSCRIPTIONS_NOT_SUPPORTED": 0x9E,
    "CONNECTION_RATE_EXCEEDED": 0x9F,
    "MAXIMUM_CONNECT_TIME": 0xA0,
    "SUBSCRIPTION_IDENTIFIERS_NOT_SUPPORTED": 0xA1,
    "WILDCARD_SUBSCRIPTIONS_NOT_SUPPORTED": 0xA2,
}


@pytest.mark.parametrize(("name", "value"), TABLE_2_6_REASON_CODES.items())
def test_table_2_6_reason_code_is_present(name: str, value: int) -> None:
    assert ReasonCode.__members__[name] == value


def test_success_value_lookup_is_canonical() -> None:
    assert ReasonCode(0x00).name == "SUCCESS"


@pytest.mark.parametrize("code", list(ReasonCode))
def test_reason_code_has_description(code: ReasonCode) -> None:
    assert code.description


@pytest.mark.parametrize(
    ("code", "is_error"),
    [
        (ReasonCode.SUCCESS, False),
        (ReasonCode.NO_MATCHING_SUBSCRIBERS, False),
        (ReasonCode.RE_AUTHENTICATE, False),
        (ReasonCode.UNSPECIFIED_ERROR, True),
        (ReasonCode.WILDCARD_SUBSCRIPTIONS_NOT_SUPPORTED, True),
    ],
)
def test_reason_code_error_classification(code: ReasonCode, is_error: bool) -> None:
    assert code.is_error() is is_error


def test_unknown_reason_code_rejected() -> None:
    with pytest.raises(ValueError):
        ReasonCode(0x03)


def test_mqtt3_connack_return_code_constants_are_preserved() -> None:
    assert CONNECTION_ACCEPTED == 0x00
    assert UNACCEPTABLE_PROTOCOL_VERSION == 0x01
    assert IDENTIFIER_REJECTED == 0x02
    assert SERVER_UNAVAILABLE == 0x03
    assert BAD_USERNAME_PASSWORD == 0x04
    assert NOT_AUTHORIZED == 0x05
