import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from amqtt.adapters import BufferReader, BufferWriter
from amqtt.broker import Broker, BrokerContext
from amqtt.mqtt3.protocol.broker_handler import BrokerProtocolHandler as MQTT3BrokerProtocolHandler
from amqtt.mqtt5.protocol.broker_handler import BrokerProtocolHandler as MQTT5BrokerProtocolHandler
from amqtt.session import Session

V3_CONNECT = b"\x10\x12\x00\x04MQTT\x04\x02\x00\x00\x00\x06client"
V5_CONNECT = b"\x10\x13\x00\x04MQTT\x05\x02\x00\x00\x00\x00\x06client"
UNKNOWN_VERSION_CONNECT = b"\x10\x12\x00\x04MQTT\x06\x02\x00\x00\x00\x06client"


@pytest.mark.asyncio
async def test_init_handler_from_connect_selects_mqtt5_handler() -> None:
    broker = _make_broker()
    writer = BufferWriter()
    handler = object()
    session = Session()

    with (
        patch("amqtt.broker.MQTT5BrokerProtocolHandler.init_from_connect", new_callable=AsyncMock) as mqtt5_init,
        patch("amqtt.broker.MQTT3BrokerProtocolHandler.init_from_connect", new_callable=AsyncMock) as mqtt3_init,
    ):
        mqtt5_init.return_value = (handler, session)

        selected_handler, selected_session = await broker._init_handler_from_connect(BufferReader(V5_CONNECT), writer)  # noqa: SLF001

    assert selected_handler is handler
    assert selected_session is session
    mqtt5_init.assert_awaited_once()
    mqtt3_init.assert_not_awaited()
    forwarded_reader = mqtt5_init.await_args.args[0]
    assert await forwarded_reader.read() == V5_CONNECT


@pytest.mark.asyncio
@pytest.mark.parametrize("connect_packet", [V3_CONNECT, UNKNOWN_VERSION_CONNECT])
async def test_init_handler_from_connect_keeps_non_mqtt5_on_mqtt3_handler(connect_packet: bytes) -> None:
    broker = _make_broker()
    writer = BufferWriter()
    handler = object()
    session = Session()

    with (
        patch("amqtt.broker.MQTT5BrokerProtocolHandler.init_from_connect", new_callable=AsyncMock) as mqtt5_init,
        patch("amqtt.broker.MQTT3BrokerProtocolHandler.init_from_connect", new_callable=AsyncMock) as mqtt3_init,
    ):
        mqtt3_init.return_value = (handler, session)

        selected_handler, selected_session = await broker._init_handler_from_connect(BufferReader(connect_packet), writer)  # noqa: SLF001

    assert selected_handler is handler
    assert selected_session is session
    mqtt3_init.assert_awaited_once()
    mqtt5_init.assert_not_awaited()
    forwarded_reader = mqtt3_init.await_args.args[0]
    assert await forwarded_reader.read() == connect_packet


@pytest.mark.asyncio
async def test_create_offline_session_defaults_to_mqtt3_handler() -> None:
    broker = _make_broker()

    handler, session = broker.create_offline_session("client")

    assert isinstance(handler, MQTT3BrokerProtocolHandler)
    assert session.client_id == "client"
    assert session.mqtt_version == 4
    assert session.transitions.is_disconnected()


@pytest.mark.asyncio
async def test_create_offline_session_selects_mqtt5_handler() -> None:
    broker = _make_broker()

    handler, session = broker.create_offline_session("client", mqtt_version=5)

    assert isinstance(handler, MQTT5BrokerProtocolHandler)
    assert session.client_id == "client"
    assert session.mqtt_version == 5
    assert session.transitions.is_disconnected()


@pytest.mark.asyncio
async def test_broker_context_add_subscription_can_create_mqtt5_offline_session() -> None:
    broker = _make_broker()
    context = BrokerContext(broker)

    await context.add_subscription("client", None, None, mqtt_version=5)

    session, handler = broker.sessions["client"]
    assert isinstance(handler, MQTT5BrokerProtocolHandler)
    assert session.client_id == "client"
    assert session.mqtt_version == 5
    assert session.transitions.is_disconnected()


def _make_broker() -> Broker:
    broker = object.__new__(Broker)
    broker.plugins_manager = object()
    broker._loop = asyncio.get_running_loop()  # noqa: SLF001
    broker._sessions = {}  # noqa: SLF001
    return broker
