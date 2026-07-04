from amqtt.constants import MQTT_PROTOCOL_LEVEL_3_1_1, MQTT_PROTOCOL_LEVEL_5
from amqtt.session import (
    MQTT5_DEFAULT_RECEIVE_MAXIMUM,
    MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL,
    MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM,
    Session,
)


def test_session_constructor_defaults_to_mqtt3_with_v5_state() -> None:
    session = Session()

    assert session.mqtt_version == MQTT_PROTOCOL_LEVEL_3_1_1
    assert session.session_expiry_interval == MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL
    assert session.receive_maximum == MQTT5_DEFAULT_RECEIVE_MAXIMUM
    assert session.topic_alias_maximum == MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM
    assert session.topic_alias_map == {}
    assert session.subscription_identifiers == {}
    assert session.inflight_qos2_count == 0
    assert session.maximum_packet_size is None


def test_session_v5_mutable_state_is_per_session() -> None:
    session = Session()
    other_session = Session()

    session.mqtt_version = MQTT_PROTOCOL_LEVEL_5
    session.topic_alias_map[1] = "sensor/temperature"
    session.subscription_identifiers["sensor/#"] = 7

    assert other_session.topic_alias_map == {}
    assert other_session.subscription_identifiers == {}
