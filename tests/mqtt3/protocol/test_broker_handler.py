import asyncio
from typing import Any

import pytest

from amqtt.adapters import BufferReader, BufferWriter
from amqtt.errors import MQTTError
from amqtt.events import MQTTEvents
from amqtt.mqtt3.connack import (
    BAD_USERNAME_PASSWORD,
    CONNECTION_ACCEPTED,
    IDENTIFIER_REJECTED,
    NOT_AUTHORIZED,
    UNACCEPTABLE_PROTOCOL_VERSION,
)
from amqtt.mqtt3.connect import ConnectPacket, ConnectPayload, ConnectVariableHeader
from amqtt.mqtt3.disconnect import DisconnectPacket
from amqtt.mqtt3.packet import PacketIdVariableHeader
from amqtt.mqtt3.pingreq import PingReqPacket
from amqtt.mqtt3.protocol.broker_handler import BrokerProtocolHandler
from amqtt.mqtt3.subscribe import SubscribePacket, SubscribePayload
from amqtt.mqtt3.unsubscribe import UnsubscribePacket, UnubscribePayload
from amqtt.protocol import ClientDisconnect, SubscriptionRequest, SubscriptionTopic, UnsubscriptionRequest
from amqtt.session import Session


class DummyPluginManager:
    def __init__(self) -> None:
        self.events: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def fire_event(self, *args: Any, **kwargs: Any) -> None:
        self.events.append((args, kwargs))


class RecordingWriter(BufferWriter):
    def __init__(self, peer_info: tuple[str, int] | None = ("127.0.0.1", 1883)) -> None:
        super().__init__()
        self.peer_info = peer_info
        self.closed = False

    def get_peer_info(self) -> tuple[str, int] | None:
        return self.peer_info

    async def close(self) -> None:
        self.closed = True


def make_session() -> Session:
    session = Session()
    session.client_id = "client-id"
    session.parent = 1
    return session


def make_handler(session: Session | None = None) -> BrokerProtocolHandler:
    handler = BrokerProtocolHandler(DummyPluginManager(), session)
    handler.writer = RecordingWriter()
    return handler


def make_connect(
    *,
    flags: int = ConnectVariableHeader.CLEAN_SESSION_FLAG,
    proto_name: str = "MQTT",
    proto_level: int = 4,
    keep_alive: int = 10,
    client_id: str | None = "client-id",
    client_id_is_random: bool = False,
    will_topic: str | None = None,
    will_message: bytes | None = None,
    username: str | None = None,
    password: str | None = None,
) -> ConnectPacket:
    variable_header = ConnectVariableHeader(flags, keep_alive, proto_name, proto_level)
    payload = ConnectPayload(client_id, will_topic, will_message, username, password)
    payload.client_id_is_random = client_id_is_random
    return ConnectPacket(variable_header=variable_header, payload=payload)


async def init_handler_from_packet(
    monkeypatch: pytest.MonkeyPatch,
    packet: ConnectPacket,
    writer: RecordingWriter | None = None,
) -> tuple[BrokerProtocolHandler, Session, DummyPluginManager, RecordingWriter]:
    plugin_manager = DummyPluginManager()
    writer = writer or RecordingWriter()

    async def fake_from_stream(reader: BufferReader) -> ConnectPacket:
        return packet

    monkeypatch.setattr(ConnectPacket, "from_stream", staticmethod(fake_from_stream))
    handler, session = await BrokerProtocolHandler.init_from_connect(BufferReader(b""), writer, plugin_manager)
    return handler, session, plugin_manager, writer


async def init_handler_raising_from_packet(
    monkeypatch: pytest.MonkeyPatch,
    packet: ConnectPacket,
    writer: RecordingWriter | None = None,
) -> tuple[DummyPluginManager, RecordingWriter]:
    plugin_manager = DummyPluginManager()
    writer = writer or RecordingWriter()

    async def fake_from_stream(reader: BufferReader) -> ConnectPacket:
        return packet

    monkeypatch.setattr(ConnectPacket, "from_stream", staticmethod(fake_from_stream))
    with pytest.raises(MQTTError):
        await BrokerProtocolHandler.init_from_connect(BufferReader(b""), writer, plugin_manager)
    return plugin_manager, writer


@pytest.mark.asyncio
async def test_wait_disconnect_returns_none_without_waiter() -> None:
    assert await make_handler(make_session()).wait_disconnect() is None


@pytest.mark.asyncio
async def test_handle_disconnect_resolves_waiter_and_resets_it() -> None:
    handler = make_handler(make_session())
    waiter: asyncio.Future[ClientDisconnect | None] = asyncio.Future()
    packet = DisconnectPacket()
    handler._disconnect_waiter = waiter

    await handler.handle_disconnect(packet)

    result = waiter.result()
    assert result is not None
    assert result.is_clean is True
    assert result.packet is packet
    assert handler._disconnect_waiter is None


@pytest.mark.asyncio
async def test_handle_connection_closed_resolves_waiter_with_none() -> None:
    handler = make_handler(make_session())
    waiter: asyncio.Future[ClientDisconnect | None] = asyncio.Future()
    handler._disconnect_waiter = waiter

    await handler.handle_connection_closed()

    result = waiter.result()
    assert result is not None
    assert result.is_clean is False
    assert result.packet is None
    assert handler._disconnect_waiter is None


@pytest.mark.asyncio
async def test_stop_resolves_disconnect_waiter_and_clears_pending_queues() -> None:
    handler = make_handler(make_session())
    waiter: asyncio.Future[ClientDisconnect | None] = asyncio.Future()
    handler._disconnect_waiter = waiter
    await handler._pending_subscriptions.put(SubscriptionRequest(1, [SubscriptionTopic("topic/a", 0)]))
    await handler._pending_unsubscriptions.put(UnsubscriptionRequest(2, ["topic/b"]))

    await handler.stop()

    assert waiter.result() is None
    assert handler._disconnect_waiter is None
    assert handler._pending_subscriptions.empty()
    assert handler._pending_unsubscriptions.empty()
    assert handler.writer is not None
    assert handler.writer.closed is True


@pytest.mark.asyncio
async def test_handle_connect_resolves_disconnect_waiter() -> None:
    handler = make_handler(make_session())
    waiter: asyncio.Future[ClientDisconnect | None] = asyncio.Future()
    handler._disconnect_waiter = waiter

    await handler.handle_connect(make_connect())

    assert waiter.result() is None


@pytest.mark.asyncio
async def test_handle_pingreq_sends_pingresp() -> None:
    handler = make_handler(make_session())

    await handler.handle_pingreq(PingReqPacket())

    assert handler.writer is not None
    assert handler.writer.get_buffer() == b"\xd0\x00"


@pytest.mark.parametrize(
    "packet",
    [
        SubscribePacket(payload=SubscribePayload([("topic/a", 0)])),
        SubscribePacket(variable_header=PacketIdVariableHeader(1)),
    ],
)
@pytest.mark.asyncio
async def test_handle_subscribe_rejects_uninitialized_packets(packet: SubscribePacket) -> None:
    handler = make_handler(make_session())

    with pytest.raises(MQTTError, match="SUBSCRIBE packet"):
        await handler.handle_subscribe(packet)


@pytest.mark.asyncio
async def test_handle_subscribe_queues_subscription() -> None:
    handler = make_handler(make_session())

    await handler.handle_subscribe(SubscribePacket.build([("topic/a", 0), ("topic/b", 1)], 7))
    subscription = await handler.get_next_pending_subscription()

    assert subscription.packet_id == 7
    assert subscription.topics == [SubscriptionTopic("topic/a", 0), SubscriptionTopic("topic/b", 1)]


@pytest.mark.parametrize(
    "packet",
    [
        UnsubscribePacket(payload=UnubscribePayload(["topic/a"])),
        UnsubscribePacket(variable_header=PacketIdVariableHeader(1)),
    ],
)
@pytest.mark.asyncio
async def test_handle_unsubscribe_rejects_uninitialized_packets(packet: UnsubscribePacket) -> None:
    handler = make_handler(make_session())

    with pytest.raises(MQTTError, match="UNSUBSCRIBE packet"):
        await handler.handle_unsubscribe(packet)


@pytest.mark.asyncio
async def test_handle_unsubscribe_queues_unsubscription() -> None:
    handler = make_handler(make_session())

    await handler.handle_unsubscribe(UnsubscribePacket.build(["topic/a", "topic/b"], 8))
    unsubscription = await handler.get_next_pending_unsubscription()

    assert unsubscription.packet_id == 8
    assert unsubscription.topics == ["topic/a", "topic/b"]


@pytest.mark.asyncio
async def test_acknowledge_subscription_and_unsubscription_write_packets() -> None:
    handler = make_handler(make_session())

    await handler.mqtt_acknowledge_subscription(7, [0, 1])
    await handler.mqtt_acknowledge_unsubscription(8)

    assert handler.writer is not None
    assert handler.writer.get_buffer() == b"\x90\x04\x00\x07\x00\x01\xb0\x02\x00\x08"


@pytest.mark.asyncio
async def test_connack_authorize_requires_session() -> None:
    handler = make_handler()

    with pytest.raises(MQTTError, match="Session is not initialized"):
        await handler.mqtt_connack_authorize(True)


@pytest.mark.parametrize(
    ("authorize", "return_code"),
    [
        (True, CONNECTION_ACCEPTED),
        (False, NOT_AUTHORIZED),
    ],
)
@pytest.mark.asyncio
async def test_connack_authorize_writes_expected_return_code(authorize: bool, return_code: int) -> None:
    handler = make_handler(make_session())

    await handler.mqtt_connack_authorize(authorize)

    assert handler.writer is not None
    assert handler.writer.get_buffer() == bytes([0x20, 0x02, 0x01, return_code])


@pytest.mark.parametrize(
    ("packet", "message"),
    [
        (ConnectPacket(payload=ConnectPayload("client-id")), "variable header"),
        (ConnectPacket(variable_header=ConnectVariableHeader()), "payload"),
        (make_connect(client_id=None), "Client identifier"),
        (
            make_connect(flags=ConnectVariableHeader.CLEAN_SESSION_FLAG | ConnectVariableHeader.WILL_FLAG),
            "Will flag set",
        ),
        (
            make_connect(flags=ConnectVariableHeader.CLEAN_SESSION_FLAG | ConnectVariableHeader.RESERVED_FLAG),
            "reserved flag",
        ),
        (make_connect(proto_name="MQIsdp"), "Incorrect protocol name"),
    ],
)
@pytest.mark.asyncio
async def test_init_from_connect_rejects_malformed_connect_packets(
    monkeypatch: pytest.MonkeyPatch,
    packet: ConnectPacket,
    message: str,
) -> None:
    plugin_manager = DummyPluginManager()

    async def fake_from_stream(reader: BufferReader) -> ConnectPacket:
        return packet

    monkeypatch.setattr(ConnectPacket, "from_stream", staticmethod(fake_from_stream))
    with pytest.raises(MQTTError, match=message):
        await BrokerProtocolHandler.init_from_connect(BufferReader(b""), RecordingWriter(), plugin_manager)

    assert plugin_manager.events == [((MQTTEvents.PACKET_RECEIVED,), {"packet": packet})]


@pytest.mark.parametrize(
    ("packet", "return_code"),
    [
        (make_connect(proto_level=3), UNACCEPTABLE_PROTOCOL_VERSION),
        (
            make_connect(flags=ConnectVariableHeader.CLEAN_SESSION_FLAG | ConnectVariableHeader.PASSWORD_FLAG),
            BAD_USERNAME_PASSWORD,
        ),
        (
            make_connect(flags=ConnectVariableHeader.CLEAN_SESSION_FLAG | ConnectVariableHeader.USERNAME_FLAG),
            BAD_USERNAME_PASSWORD,
        ),
        (
            make_connect(
                flags=(
                    ConnectVariableHeader.CLEAN_SESSION_FLAG
                    | ConnectVariableHeader.USERNAME_FLAG
                    | ConnectVariableHeader.PASSWORD_FLAG
                ),
                username="user",
            ),
            BAD_USERNAME_PASSWORD,
        ),
        (make_connect(flags=0, client_id="generated", client_id_is_random=True), IDENTIFIER_REJECTED),
    ],
)
@pytest.mark.asyncio
async def test_init_from_connect_sends_connack_then_rejects_invalid_connections(
    monkeypatch: pytest.MonkeyPatch,
    packet: ConnectPacket,
    return_code: int,
) -> None:
    plugin_manager, writer = await init_handler_raising_from_packet(monkeypatch, packet)

    assert writer.closed is True
    assert writer.get_buffer() == bytes([0x20, 0x02, 0x00, return_code])
    assert len(plugin_manager.events) == 2
    assert plugin_manager.events[0] == ((MQTTEvents.PACKET_RECEIVED,), {"packet": packet})
    assert plugin_manager.events[1][0] == (MQTTEvents.PACKET_SENT,)
    assert plugin_manager.events[1][1]["packet"].return_code == return_code


@pytest.mark.asyncio
async def test_init_from_connect_returns_handler_and_populates_session(monkeypatch: pytest.MonkeyPatch) -> None:
    packet = make_connect(
        flags=(
            ConnectVariableHeader.CLEAN_SESSION_FLAG
            | ConnectVariableHeader.WILL_FLAG
            | ConnectVariableHeader.USERNAME_FLAG
            | ConnectVariableHeader.PASSWORD_FLAG
        ),
        keep_alive=30,
        will_topic="will/topic",
        will_message=b"gone",
        username="user",
        password="password",
    )

    handler, session, plugin_manager, writer = await init_handler_from_packet(monkeypatch, packet)

    assert isinstance(handler, BrokerProtocolHandler)
    assert session.client_id == "client-id"
    assert session.clean_session is True
    assert session.will_flag is True
    assert session.will_retain is False
    assert session.will_qos == 0
    assert session.will_topic == "will/topic"
    assert session.will_message == b"gone"
    assert session.username == "user"
    assert session.password == "password"
    assert session.remote_address == "127.0.0.1"
    assert session.remote_port == 1883
    assert session.keep_alive == 30
    assert writer.closed is False
    assert plugin_manager.events == [((MQTTEvents.PACKET_RECEIVED,), {"packet": packet})]
