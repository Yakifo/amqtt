from __future__ import annotations

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest

from amqtt.adapters import BufferReader, BufferWriter
from amqtt.constants import MQTT_PROTOCOL_LEVEL_5
from amqtt.contexts import BrokerConfig
from amqtt.errors import NoDataError
from amqtt.mqtt5.connect import ConnectPacket
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    CONTENT_TYPE,
    PACKET_CONNECT,
    PACKET_WILL,
    RECEIVE_MAXIMUM,
    REQUEST_PROBLEM_INFORMATION,
    SESSION_EXPIRY_INTERVAL,
    USER_PROPERTY,
    WILL_DELAY_INTERVAL,
)
from amqtt.mqtt5.protocol.broker_handler import BrokerProtocolHandler
from amqtt.session import Session


class _StrictBufferReader(BufferReader):
    def __init__(self, buffer: bytes) -> None:
        super().__init__(buffer)
        self._raise_on_empty_read = buffer == b""

    async def read(self, n: int = -1) -> bytes:
        data = await super().read(n)
        if self._raise_on_empty_read and data == b"":
            msg = "No more data"
            raise NoDataError(msg)
        return data


@pytest.fixture(scope="session")
def make_reader() -> Callable[[bytes], BufferReader]:
    def _make_reader(data: bytes) -> BufferReader:
        return _StrictBufferReader(data)

    return _make_reader


@pytest.fixture
def v5_connect_packet() -> ConnectPacket:
    properties = Properties(packet_name=PACKET_CONNECT)
    properties.set(SESSION_EXPIRY_INTERVAL, 300)
    properties.set(RECEIVE_MAXIMUM, 10)
    properties.set(REQUEST_PROBLEM_INFORMATION, 0)
    properties.set(USER_PROPERTY, ("source", "test"))

    will_properties = Properties(packet_name=PACKET_WILL)
    will_properties.set(WILL_DELAY_INTERVAL, 5)
    will_properties.set(CONTENT_TYPE, "text/plain")
    will_properties.set(USER_PROPERTY, ("wk", "wv"))

    return ConnectPacket.build(
        "client-1",
        clean_start=True,
        keep_alive=60,
        properties=properties,
        will_topic="will/topic",
        will_message=b"offline",
        will_qos=1,
        will_retain=True,
        will_properties=will_properties,
        username="user",
        password=b"\x00secret",
    )


@pytest.fixture
def mock_v5_session() -> Session:
    session = Session()
    session.mqtt_version = MQTT_PROTOCOL_LEVEL_5
    return session


@pytest.fixture
async def mock_broker_handler(
    make_reader: Callable[[bytes], BufferReader],
    mock_v5_session: Session,
) -> BrokerProtocolHandler:
    plugins_manager = AsyncMock()
    handler = BrokerProtocolHandler(plugins_manager, loop=asyncio.get_running_loop(), config=BrokerConfig())
    handler.attach(mock_v5_session, make_reader(b""), BufferWriter())
    return handler


@pytest.fixture
def mock_client_handler(make_reader: Callable[[bytes], BufferReader], mock_v5_session: Session) -> AsyncMock:
    handler = AsyncMock()
    handler.session = mock_v5_session
    handler.reader = make_reader(b"")
    handler.writer = BufferWriter()
    handler.plugins_manager = AsyncMock()
    return handler
