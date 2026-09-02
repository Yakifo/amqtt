import asyncio
from contextlib import suppress
from typing import Any

import pytest

from amqtt.adapters import BufferWriter, StreamReaderAdapter, StreamWriterAdapter
from amqtt.client import MQTTClient
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket, ConnectPayload, ConnectVariableHeader
from amqtt.mqtt.constants import QOS_1, QOS_2
from amqtt.mqtt.packet import PUBREL, PUBLISH
from amqtt.mqtt.protocol.handler import ProtocolHandler
from amqtt.mqtt.puback import PubackPacket
from amqtt.mqtt.pubcomp import PubcompPacket
from amqtt.mqtt.publish import PublishPacket
from amqtt.mqtt.pubrec import PubrecPacket
from amqtt.mqtt.pubrel import PubrelPacket
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.session import OutgoingApplicationMessage, Session


class DummyPluginManager:
    async def fire_event(self, *args: Any, **kwargs: Any) -> None:
        pass


async def wait_for_waiter(handler: ProtocolHandler[Any], waiter_name: str, packet_id: int) -> None:
    for _ in range(50):
        if packet_id in getattr(handler, waiter_name):
            return
        await asyncio.sleep(0)
    pytest.fail(f"timed out waiting for {waiter_name}[{packet_id}]")


async def wait_for_output(writer: BufferWriter) -> bytes:
    for _ in range(50):
        output = writer.get_buffer()
        if output:
            return output
        await asyncio.sleep(0)
    return writer.get_buffer()


def first_packet_type(buffer: bytes) -> int:
    if not buffer:
        pytest.fail("expected packet to be resent after reconnect, but no packet was written")
    return buffer[0] >> 4


async def raw_connect(client_id: str) -> tuple[StreamReaderAdapter, StreamWriterAdapter, ConnackPacket]:
    stream_reader, stream_writer = await asyncio.open_connection("127.0.0.1", 1883)
    reader = StreamReaderAdapter(stream_reader)
    writer = StreamWriterAdapter(stream_writer)

    variable_header = ConnectVariableHeader()
    variable_header.keep_alive = 10
    variable_header.clean_session_flag = False
    payload = ConnectPayload()
    payload.client_id = client_id
    await ConnectPacket(variable_header=variable_header, payload=payload).to_stream(writer)

    connack = await asyncio.wait_for(ConnackPacket.from_stream(reader), timeout=1)
    assert connack.return_code == 0
    return reader, writer, connack


async def raw_subscribe(reader: StreamReaderAdapter, writer: StreamWriterAdapter, topic: str, qos: int) -> None:
    await SubscribePacket.build([(topic, qos)], packet_id=1).to_stream(writer)
    suback = await asyncio.wait_for(SubackPacket.from_stream(reader), timeout=1)
    assert suback.payload is not None
    assert suback.payload.return_codes == [qos]


async def wait_for_session_state(broker: Any, client_id: str, state: str) -> None:
    for _ in range(100):
        session_entry = broker.sessions.get(client_id)
        if session_entry is not None and session_entry[0].transitions.state == state:
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"timed out waiting for {client_id} session to become {state}")


@pytest.mark.asyncio
async def test_qos1_reconnect_while_waiting_for_puback_resends_publish() -> None:
    packet_id = 1
    session = Session()
    message = OutgoingApplicationMessage(packet_id, "/topic", QOS_1, b"payload", False)
    first_handler = ProtocolHandler(DummyPluginManager(), session)
    first_handler.writer = BufferWriter()

    first_flow = asyncio.create_task(first_handler._handle_qos1_message_flow(message))
    await wait_for_waiter(first_handler, "_puback_waiters", packet_id)

    await first_handler.stop()
    with suppress(asyncio.CancelledError):
        await first_flow
    assert session.inflight_out.get(packet_id) is message

    reconnect_handler = ProtocolHandler(DummyPluginManager(), session)
    reconnect_writer = BufferWriter()
    reconnect_handler.writer = reconnect_writer

    retry_flow = asyncio.create_task(reconnect_handler._retry_deliveries())
    try:
        output = await wait_for_output(reconnect_writer)
        assert first_packet_type(output) == PUBLISH

        await wait_for_waiter(reconnect_handler, "_puback_waiters", packet_id)
        await reconnect_handler.handle_puback(PubackPacket.build(packet_id))
        await retry_flow
    finally:
        retry_flow.cancel()
        with suppress(asyncio.CancelledError):
            await retry_flow


@pytest.mark.asyncio
async def test_broker_qos1_reconnect_without_puback_republishes(broker_fixture: Any) -> None:
    broker = broker_fixture
    subscriber_id = "qos1-no-puback-subscriber"
    topic = "/qos1/no-puback/reconnect"
    payload = b"payload"
    first_writer: StreamWriterAdapter | None = None
    second_writer: StreamWriterAdapter | None = None
    publisher = MQTTClient(client_id="qos1-no-puback-publisher")

    try:
        first_reader, first_writer, connack = await raw_connect(subscriber_id)
        assert connack.session_parent == 0
        await raw_subscribe(first_reader, first_writer, topic, QOS_1)

        assert await publisher.connect("mqtt://127.0.0.1/") == 0
        await publisher.publish(topic, payload, QOS_1)

        first_publish = await asyncio.wait_for(PublishPacket.from_stream(first_reader), timeout=2)
        assert first_publish.topic_name == topic
        assert first_publish.data == payload
        assert first_publish.qos == QOS_1
        assert first_publish.dup_flag is False

        await first_writer.close()
        first_writer = None
        await wait_for_session_state(broker, subscriber_id, "disconnected")

        second_reader, second_writer, connack = await raw_connect(subscriber_id)
        assert connack.session_parent == 1

        republished = await asyncio.wait_for(PublishPacket.from_stream(second_reader), timeout=2)
        assert republished.topic_name == topic
        assert republished.data == payload
        assert republished.qos == QOS_1
        assert republished.dup_flag is True
        assert republished.packet_id is not None
        await PubackPacket.build(republished.packet_id).to_stream(second_writer)
    finally:
        if first_writer is not None:
            await first_writer.close()
        if second_writer is not None:
            await second_writer.close()
        with suppress(Exception):
            await publisher.disconnect()


@pytest.mark.asyncio
async def test_broker_qos2_reconnect_without_pubcomp_resends_pubrel(broker_fixture: Any) -> None:
    broker = broker_fixture
    subscriber_id = "qos2-no-pubcomp-subscriber"
    topic = "/qos2/no-pubcomp/reconnect"
    payload = b"qos2 resend payload"
    first_writer: StreamWriterAdapter | None = None
    second_writer: StreamWriterAdapter | None = None
    publisher = MQTTClient(client_id="qos2-no-pubcomp-publisher")

    try:
        first_reader, first_writer, connack = await raw_connect(subscriber_id)
        assert connack.session_parent == 0
        await raw_subscribe(first_reader, first_writer, topic, QOS_2)

        assert await publisher.connect("mqtt://127.0.0.1/") == 0
        await publisher.publish(topic, payload, QOS_2)

        first_publish = await asyncio.wait_for(PublishPacket.from_stream(first_reader), timeout=2)
        assert first_publish.topic_name == topic
        assert first_publish.data == payload
        assert first_publish.qos == QOS_2
        assert first_publish.dup_flag is False
        assert first_publish.packet_id is not None

        await PubrecPacket.build(first_publish.packet_id).to_stream(first_writer)
        first_pubrel = await asyncio.wait_for(PubrelPacket.from_stream(first_reader), timeout=2)
        assert first_pubrel.packet_id == first_publish.packet_id

        await first_writer.close()
        first_writer = None
        await wait_for_session_state(broker, subscriber_id, "disconnected")

        second_reader, second_writer, connack = await raw_connect(subscriber_id)
        assert connack.session_parent == 1

        resent_pubrel = await asyncio.wait_for(PubrelPacket.from_stream(second_reader), timeout=2)
        assert resent_pubrel.packet_id == first_publish.packet_id

        await PubcompPacket.build(resent_pubrel.packet_id).to_stream(second_writer)
    finally:
        if first_writer is not None:
            await first_writer.close()
        if second_writer is not None:
            await second_writer.close()
        with suppress(Exception):
            await publisher.disconnect()


@pytest.mark.asyncio
async def test_qos2_reconnect_while_waiting_for_pubcomp_resends_pubrel() -> None:
    packet_id = 1
    session = Session()
    message = OutgoingApplicationMessage(packet_id, "/topic", QOS_2, b"payload", False)
    first_handler = ProtocolHandler(DummyPluginManager(), session)
    first_handler.writer = BufferWriter()

    first_flow = asyncio.create_task(first_handler._handle_qos2_message_flow(message))
    await wait_for_waiter(first_handler, "_pubrec_waiters", packet_id)

    await first_handler.handle_pubrec(PubrecPacket.build(packet_id))
    await wait_for_waiter(first_handler, "_pubcomp_waiters", packet_id)

    await first_handler.stop()
    with suppress(asyncio.CancelledError):
        await first_flow
    assert session.inflight_out[packet_id] is message

    reconnect_handler = ProtocolHandler(DummyPluginManager(), session)
    reconnect_writer = BufferWriter()
    reconnect_handler.writer = reconnect_writer

    retry_flow = asyncio.create_task(reconnect_handler._retry_deliveries())
    try:
        output = await wait_for_output(reconnect_writer)
        assert first_packet_type(output) == PUBREL

        await wait_for_waiter(reconnect_handler, "_pubcomp_waiters", packet_id)
        await reconnect_handler.handle_pubcomp(PubcompPacket.build(packet_id))
        await retry_flow
    finally:
        retry_flow.cancel()
        with suppress(asyncio.CancelledError):
            await retry_flow
