from __future__ import annotations

import pytest

from amqtt.adapters import BufferReader, BufferWriter
from amqtt.constants import MQTT_PROTOCOL_LEVEL_5
from amqtt.errors import NoDataError
from amqtt.mqtt5.connect import ConnectPacket
from amqtt.mqtt5.protocol.broker_handler import BrokerProtocolHandler
from amqtt.session import (
    MQTT5_DEFAULT_RECEIVE_MAXIMUM,
    MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL,
    MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM,
)


@pytest.mark.asyncio
async def test_make_reader_empty_buffer_raises_on_read(make_reader) -> None:
    reader = make_reader(b"")

    assert isinstance(reader, BufferReader)
    with pytest.raises(NoDataError):
        await reader.read(1)


def test_v5_connect_packet_fixture_is_fully_populated(v5_connect_packet) -> None:
    assert isinstance(v5_connect_packet, ConnectPacket)
    assert v5_connect_packet.proto_level == MQTT_PROTOCOL_LEVEL_5
    assert v5_connect_packet.clean_start_flag is True
    assert v5_connect_packet.client_id == "client-1"
    assert v5_connect_packet.will_flag is True
    assert v5_connect_packet.will_topic == "will/topic"
    assert v5_connect_packet.will_message == b"offline"
    assert v5_connect_packet.username == "user"
    assert v5_connect_packet.password == b"\x00secret"


def test_mock_v5_session_uses_spec_default_state(mock_v5_session) -> None:
    assert mock_v5_session.mqtt_version == MQTT_PROTOCOL_LEVEL_5
    assert mock_v5_session.session_expiry_interval == MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL
    assert mock_v5_session.receive_maximum == MQTT5_DEFAULT_RECEIVE_MAXIMUM
    assert mock_v5_session.topic_alias_maximum == MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM
    assert mock_v5_session.topic_alias_map == {}
    assert mock_v5_session.subscription_identifiers == {}
    assert mock_v5_session.inflight_qos2_count == 0
    assert mock_v5_session.maximum_packet_size is None


@pytest.mark.asyncio
async def test_mock_broker_handler_is_attached_to_memory_streams(mock_broker_handler) -> None:
    assert isinstance(mock_broker_handler, BrokerProtocolHandler)
    assert mock_broker_handler.session is not None
    assert mock_broker_handler.session.mqtt_version == MQTT_PROTOCOL_LEVEL_5
    assert isinstance(mock_broker_handler.reader, BufferReader)
    assert isinstance(mock_broker_handler.writer, BufferWriter)


def test_mock_client_handler_is_wired_to_memory_streams(mock_client_handler) -> None:
    assert mock_client_handler.session.mqtt_version == MQTT_PROTOCOL_LEVEL_5
    assert isinstance(mock_client_handler.reader, BufferReader)
    assert isinstance(mock_client_handler.writer, BufferWriter)
