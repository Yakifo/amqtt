import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any

import pytest

from amqtt.adapters import BufferReader, BufferWriter
from amqtt.errors import AMQTTError, ProtocolHandlerError, PubAckTimeoutError
from amqtt.events import MQTTEvents
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.protocol import handler as handler_module
from amqtt.mqtt.protocol.handler import ProtocolHandler
from amqtt.mqtt.puback import PubackPacket
from amqtt.mqtt.pubcomp import PubcompPacket
from amqtt.mqtt.publish import PublishPacket
from amqtt.mqtt.pubrec import PubrecPacket
from amqtt.mqtt.pubrel import PubrelPacket
from amqtt.session import IncomingApplicationMessage, OutgoingApplicationMessage, Session


class DummyPluginManager:
    def __init__(self) -> None:
        self.events: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def fire_event(self, *args: Any, **kwargs: Any) -> None:
        self.events.append((args, kwargs))


class ResetWriter(BufferWriter):
    def write(self, data: bytes) -> None:
        raise ConnectionResetError


class CancelledPacket:
    async def to_stream(self, writer: BufferWriter) -> None:
        raise asyncio.CancelledError


class RecordingProtocolHandler(ProtocolHandler[Any]):
    def __init__(self, plugins_manager: DummyPluginManager, session: Session) -> None:
        super().__init__(plugins_manager, session)
        self.connection_closed_calls = 0
        self.stopped = False

    async def handle_connection_closed(self) -> None:
        self.connection_closed_calls += 1

    async def stop(self) -> None:
        self.stopped = True


class DuplicatePacketIdSession(Session):
    @property
    def next_packet_id(self) -> int:
        return 1


def make_session() -> Session:
    session = Session()
    session.client_id = "test-client"
    return session


def make_handler(session: Session | None = None) -> ProtocolHandler[Any]:
    handler = ProtocolHandler(DummyPluginManager(), session)
    handler.writer = BufferWriter()
    return handler


@pytest.mark.asyncio
async def test_start_requires_an_attached_session() -> None:
    handler = make_handler()

    with pytest.raises(ProtocolHandlerError, match="not attached"):
        await handler.start()


def test_attach_rejects_handler_that_already_has_session() -> None:
    handler = make_handler(make_session())

    with pytest.raises(ProtocolHandlerError, match="already attached"):
        handler.attach(make_session(), BufferReader(b""), BufferWriter())


@pytest.mark.parametrize(
    "method_name",
    [
        "handle_connack",
        "handle_connect",
        "handle_subscribe",
        "handle_unsubscribe",
        "handle_suback",
        "handle_unsuback",
        "handle_pingresp",
        "handle_pingreq",
        "handle_disconnect",
    ],
)
@pytest.mark.asyncio
async def test_base_packet_handlers_require_a_session(method_name: str) -> None:
    handler = make_handler()

    with pytest.raises(AMQTTError, match="Session is not initialized"):
        await getattr(handler, method_name)(object())


@pytest.mark.parametrize(
    "method_name",
    [
        "handle_connack",
        "handle_connect",
        "handle_subscribe",
        "handle_unsubscribe",
        "handle_suback",
        "handle_unsuback",
        "handle_pingresp",
        "handle_pingreq",
        "handle_disconnect",
    ],
)
@pytest.mark.asyncio
async def test_base_packet_handlers_are_noops_with_a_session(method_name: str) -> None:
    handler = make_handler(make_session())

    await getattr(handler, method_name)(object())


@pytest.mark.asyncio
async def test_base_connection_closed_requires_a_session() -> None:
    handler = make_handler()

    with pytest.raises(AMQTTError, match="Session is not initialized"):
        await handler.handle_connection_closed()


def test_base_timeout_callbacks_require_a_session() -> None:
    handler = make_handler()

    with pytest.raises(AMQTTError, match="Session is not initialized"):
        handler.handle_write_timeout()
    with pytest.raises(AMQTTError, match="Session is not initialized"):
        handler.handle_read_timeout()


def test_base_timeout_callbacks_are_noops_with_a_session() -> None:
    handler = make_handler(make_session())

    handler.handle_write_timeout()
    handler.handle_read_timeout()


def test_stop_waiters_rejects_non_future_waiters() -> None:
    handler = make_handler(make_session())
    handler._puback_waiters[1] = object()

    with pytest.raises(AMQTTError, match="Waiter is not"):
        handler._stop_waiters()


@pytest.mark.asyncio
async def test_stop_waiters_cancels_all_pending_waiters() -> None:
    handler = make_handler(make_session())
    waiters = [asyncio.Future() for _ in range(4)]
    handler._puback_waiters[1] = waiters[0]
    handler._pubrec_waiters[2] = waiters[1]
    handler._pubrel_waiters[3] = waiters[2]
    handler._pubcomp_waiters[4] = waiters[3]

    handler._stop_waiters()

    assert all(waiter.cancelled() for waiter in waiters)


@pytest.mark.asyncio
async def test_mqtt_publish_rejects_duplicate_outgoing_packet_id() -> None:
    session = DuplicatePacketIdSession()
    session.client_id = "test-client"
    session.inflight_out[1] = OutgoingApplicationMessage(1, "/topic", QOS_1, b"old", False)
    handler = make_handler(session)

    with pytest.raises(AMQTTError, match="same packet ID"):
        await handler.mqtt_publish("/topic", b"data", QOS_1, False)


@pytest.mark.asyncio
async def test_message_flow_rejects_unknown_qos() -> None:
    handler = make_handler(make_session())
    message = OutgoingApplicationMessage(1, "/topic", 9, b"data", False)

    with pytest.raises(AMQTTError, match="Unexpected QOS"):
        await handler._handle_message_flow(message)


@pytest.mark.asyncio
async def test_qos0_flow_validates_qos_and_session() -> None:
    handler = make_handler(make_session())

    with pytest.raises(ValueError, match="Expected QOS_0"):
        await handler._handle_qos0_message_flow(OutgoingApplicationMessage(None, "/topic", QOS_1, b"data", False))

    handler_without_session = make_handler()
    with pytest.raises(AMQTTError, match="Session is not initialized"):
        await handler_without_session._handle_qos0_message_flow(
            OutgoingApplicationMessage(None, "/topic", QOS_0, b"data", False),
        )


@pytest.mark.asyncio
async def test_qos0_incoming_duplicate_and_full_queue_are_ignored() -> None:
    session = make_session()
    handler = make_handler(session)
    duplicate = IncomingApplicationMessage(None, "/topic", QOS_0, b"data", False)
    duplicate.publish_packet = PublishPacket.build("/topic", b"data", None, True, QOS_0, False)

    await handler._handle_qos0_message_flow(duplicate)

    assert session.delivered_message_queue.empty()

    session.delivered_message_queue = asyncio.Queue(maxsize=1)
    session.delivered_message_queue.put_nowait(IncomingApplicationMessage(None, "/queued", QOS_0, b"old", False))
    incoming = IncomingApplicationMessage(None, "/topic", QOS_0, b"data", False)

    await handler._handle_qos0_message_flow(incoming)

    assert session.delivered_message_queue.qsize() == 1


@pytest.mark.asyncio
async def test_qos1_flow_validates_message_state() -> None:
    handler = make_handler(make_session())

    with pytest.raises(ValueError, match="Expected QOS_1"):
        await handler._handle_qos1_message_flow(OutgoingApplicationMessage(1, "/topic", QOS_0, b"data", False))
    with pytest.raises(ValueError, match="Packet ID"):
        await handler._handle_qos1_message_flow(OutgoingApplicationMessage(None, "/topic", QOS_1, b"data", False))

    acknowledged = OutgoingApplicationMessage(1, "/topic", QOS_1, b"data", False)
    acknowledged.puback_packet = PubackPacket.build(1)
    with pytest.raises(AMQTTError, match="already been acknowledged"):
        await handler._handle_qos1_message_flow(acknowledged)

    handler_without_session = make_handler()
    with pytest.raises(AMQTTError, match="Session is not initialized"):
        await handler_without_session._handle_qos1_message_flow(
            OutgoingApplicationMessage(1, "/topic", QOS_1, b"data", False),
        )


@pytest.mark.asyncio
async def test_qos1_outgoing_timeout_cleans_waiter_and_inflight(monkeypatch: pytest.MonkeyPatch) -> None:
    session = make_session()
    handler = make_handler(session)
    message = OutgoingApplicationMessage(7, "/topic", QOS_1, b"data", False)

    async def timeout_wait_for(awaitable: Awaitable[Any], timeout: float | None = None) -> Any:
        del timeout
        if isinstance(awaitable, asyncio.Future):
            awaitable.cancel()
        raise asyncio.TimeoutError

    monkeypatch.setattr(handler_module.asyncio, "wait_for", timeout_wait_for)

    with pytest.raises(PubAckTimeoutError, match="Timeout waiting for PUBACK"):
        await handler._handle_qos1_message_flow(message)

    assert not handler._puback_waiters
    assert 7 not in session.inflight_out


@pytest.mark.asyncio
async def test_qos2_flow_validates_message_state() -> None:
    handler = make_handler(make_session())

    with pytest.raises(ValueError, match="Expected QOS_2"):
        await handler._handle_qos2_message_flow(OutgoingApplicationMessage(1, "/topic", QOS_1, b"data", False))
    with pytest.raises(ValueError, match="Packet ID"):
        await handler._handle_qos2_message_flow(OutgoingApplicationMessage(None, "/topic", QOS_2, b"data", False))

    handler_without_session = make_handler()
    with pytest.raises(AMQTTError, match="Session is not initialized"):
        await handler_without_session._handle_qos2_message_flow(
            OutgoingApplicationMessage(1, "/topic", QOS_2, b"data", False),
        )

    acknowledged = OutgoingApplicationMessage(1, "/topic", QOS_2, b"data", False)
    acknowledged.pubrel_packet = PubrelPacket.build(1)
    acknowledged.pubcomp_packet = PubcompPacket.build(1)
    with pytest.raises(AMQTTError, match="already been acknowledged"):
        await handler._handle_qos2_message_flow(acknowledged)


@pytest.mark.asyncio
async def test_qos2_retry_with_unknown_inflight_message_raises() -> None:
    handler = make_handler(make_session())
    message = OutgoingApplicationMessage(22, "/topic", QOS_2, b"data", False)
    message.publish_packet = PublishPacket.build("/topic", b"data", 22, False, QOS_2, False)

    with pytest.raises(AMQTTError, match="Unknown inflight message"):
        await handler._handle_qos2_message_flow(message)


@pytest.mark.asyncio
async def test_qos2_duplicate_pubrec_waiter_raises() -> None:
    session = make_session()
    handler = make_handler(session)
    message = OutgoingApplicationMessage(23, "/topic", QOS_2, b"data", False)
    message.publish_packet = PublishPacket.build("/topic", b"data", 23, False, QOS_2, False)
    session.inflight_out[23] = message
    handler._pubrec_waiters[23] = asyncio.Future()

    with pytest.raises(AMQTTError, match="PUBREC waiter"):
        await handler._handle_qos2_message_flow(message)


@pytest.mark.asyncio
async def test_qos2_unknown_direction_is_ignored() -> None:
    session = make_session()
    handler = make_handler(session)
    message = OutgoingApplicationMessage(24, "/topic", QOS_2, b"data", False)
    message.direction = 99

    await handler._handle_qos2_message_flow(message)

    assert 24 not in session.inflight_out
    assert handler.writer is not None
    assert handler.writer.get_buffer() == b""


@pytest.mark.asyncio
async def test_qos2_incoming_replaces_existing_pubrel_waiter_when_flow_is_cancelled() -> None:
    session = make_session()
    handler = make_handler(session)
    old_waiter = asyncio.Future()
    handler._pubrel_waiters[25] = old_waiter
    message = IncomingApplicationMessage(25, "/topic", QOS_2, b"data", False)

    task = asyncio.create_task(handler._handle_qos2_message_flow(message))
    for _ in range(10):
        await asyncio.sleep(0)
        if handler._pubrel_waiters.get(25) is not old_waiter:
            break

    assert old_waiter.cancelled()
    assert handler._pubrel_waiters[25] is not old_waiter

    task.cancel()
    await task

    assert session.inflight_in[25] is message


@pytest.mark.parametrize(
    ("waiter_attr", "method_name", "packet_factory"),
    [
        ("_puback_waiters", "handle_puback", PubackPacket.build),
        ("_pubrec_waiters", "handle_pubrec", PubrecPacket.build),
        ("_pubrel_waiters", "handle_pubrel", PubrelPacket.build),
        ("_pubcomp_waiters", "handle_pubcomp", PubcompPacket.build),
    ],
)
@pytest.mark.asyncio
async def test_ack_handlers_resolve_known_waiters(
    waiter_attr: str,
    method_name: str,
    packet_factory: Callable[[int], Any],
) -> None:
    handler = make_handler(make_session())
    waiter: asyncio.Future[Any] = asyncio.Future()
    getattr(handler, waiter_attr)[31] = waiter
    packet = packet_factory(31)

    await getattr(handler, method_name)(packet)

    assert waiter.result() is packet


@pytest.mark.parametrize(
    ("waiter_attr", "method_name", "packet_factory"),
    [
        ("_puback_waiters", "handle_puback", PubackPacket.build),
        ("_pubrec_waiters", "handle_pubrec", PubrecPacket.build),
        ("_pubrel_waiters", "handle_pubrel", PubrelPacket.build),
        ("_pubcomp_waiters", "handle_pubcomp", PubcompPacket.build),
    ],
)
@pytest.mark.asyncio
async def test_ack_handlers_log_unknown_and_done_waiters(
    caplog: pytest.LogCaptureFixture,
    waiter_attr: str,
    method_name: str,
    packet_factory: Callable[[int], Any],
) -> None:
    handler = make_handler(make_session())
    caplog.set_level(logging.WARNING, logger="amqtt.mqtt.protocol.handler")

    await getattr(handler, method_name)(packet_factory(41))

    done_waiter: asyncio.Future[Any] = asyncio.Future()
    done_waiter.set_result(packet_factory(42))
    getattr(handler, waiter_attr)[42] = done_waiter
    await getattr(handler, method_name)(packet_factory(42))

    assert "unknown pending" in caplog.text
    assert "already done" in caplog.text


@pytest.mark.asyncio
async def test_puback_handler_requires_variable_header() -> None:
    handler = make_handler(make_session())

    with pytest.raises(ValueError, match="Variable header"):
        await handler.handle_puback(PubackPacket())


@pytest.mark.asyncio
async def test_send_packet_resets_keepalive_timer_and_fires_event() -> None:
    session = make_session()
    session.keep_alive = 10
    handler = make_handler(session)
    previous_timer = asyncio.get_running_loop().call_later(60, lambda: None)
    handler._keepalive_task = previous_timer

    await handler._send_packet(PingReqPacket())

    assert previous_timer.cancelled()
    assert handler._keepalive_task is not previous_timer
    assert handler.plugins_manager.events[-1][0] == (MQTTEvents.PACKET_SENT,)
    handler._keepalive_task.cancel()


@pytest.mark.asyncio
async def test_send_packet_handles_connection_reset() -> None:
    handler = make_handler(make_session())
    handler.writer = ResetWriter()
    called = False

    async def mark_connection_closed() -> None:
        nonlocal called
        called = True

    handler.handle_connection_closed = mark_connection_closed

    await handler._send_packet(PingReqPacket())

    assert called


@pytest.mark.asyncio
async def test_send_packet_converts_cancellation_to_protocol_error() -> None:
    handler = make_handler(make_session())

    with pytest.raises(ProtocolHandlerError, match="cancelled"):
        await handler._send_packet(CancelledPacket())


@pytest.mark.asyncio
async def test_reader_loop_requires_session_and_ready_event() -> None:
    handler = make_handler()

    with pytest.raises(AMQTTError, match="Session is not initialized"):
        await handler._reader_loop()

    handler = make_handler(make_session())
    handler._reader_ready = None
    with pytest.raises(ProtocolHandlerError, match="Reader ready"):
        await handler._reader_loop()


@pytest.mark.asyncio
async def test_reader_loop_stops_when_reader_is_missing() -> None:
    handler = make_handler(make_session())
    handler.reader = None
    handler._reader_ready = asyncio.Event()

    await handler._reader_loop()

    assert handler._reader_stopped.is_set()


@pytest.mark.asyncio
async def test_reader_loop_self_stop_does_not_wait_on_itself() -> None:
    handler = make_handler(make_session())
    handler.reader = None
    handler._reader_ready = asyncio.Event()

    task = asyncio.create_task(handler._reader_loop())
    handler._reader_task = task

    await asyncio.wait_for(task, timeout=1)

    assert handler._reader_stopped.is_set()


@pytest.mark.asyncio
async def test_reader_loop_handles_reserved_packet_then_eof() -> None:
    session = make_session()
    plugin_manager = DummyPluginManager()
    handler = RecordingProtocolHandler(plugin_manager, session)
    handler.reader = BufferReader(b"\x00\x00")
    handler.writer = BufferWriter()
    handler._reader_ready = asyncio.Event()

    await handler._reader_loop()

    assert handler.connection_closed_calls == 2
    assert handler._reader_stopped.is_set()
    assert handler.stopped is True
