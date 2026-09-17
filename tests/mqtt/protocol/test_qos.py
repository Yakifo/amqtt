import asyncio
from contextlib import suppress
from typing import Any

import pytest

from amqtt.adapters import BufferWriter, StreamReaderAdapter, StreamWriterAdapter
from amqtt.client import MQTTClient
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket, ConnectPayload, ConnectVariableHeader
from amqtt.mqtt.constants import QOS_1, QOS_2
from amqtt.mqtt.disconnect import DisconnectPacket
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


async def wait_for_client_state(client: MQTTClient, state: str) -> None:
    for _ in range(100):
        if client.session is not None and client.session.transitions.state == state:
            return
        await asyncio.sleep(0.01)
    pytest.fail(f"timed out waiting for client session to become {state}")


def server_port(server: asyncio.Server) -> int:
    assert server.sockets is not None
    return int(server.sockets[0].getsockname()[1])


async def wait_for_fake_broker_result(
    result: asyncio.Future[Any],
    server_error: asyncio.Future[None],
    label: str,
) -> Any:
    done, _ = await asyncio.wait({result, server_error}, timeout=2, return_when=asyncio.FIRST_COMPLETED)
    if server_error in done:
        server_error.result()
    if result in done:
        return result.result()
    pytest.fail(f"timed out waiting for fake broker to receive {label}")


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
async def test_client_qos1_reconnect_while_waiting_for_puback_republishes() -> None:
    topic = "/client/qos1/no-puback/reconnect"
    payload = b"client qos1 resend payload"
    loop = asyncio.get_running_loop()
    first_publish_received: asyncio.Future[PublishPacket] = loop.create_future()
    retry_publish_received: asyncio.Future[PublishPacket] = loop.create_future()
    server_error: asyncio.Future[None] = loop.create_future()
    server_writers: list[StreamWriterAdapter] = []
    connection_count = 0

    async def fake_broker(raw_reader: asyncio.StreamReader, raw_writer: asyncio.StreamWriter) -> None:
        nonlocal connection_count
        reader, writer = StreamReaderAdapter(raw_reader), StreamWriterAdapter(raw_writer)
        server_writers.append(writer)
        connection_count += 1

        try:
            await ConnectPacket.from_stream(reader)
            await ConnackPacket.build(session_parent=1 if connection_count > 1 else 0, return_code=0).to_stream(writer)

            publish = await asyncio.wait_for(PublishPacket.from_stream(reader), timeout=2)
            if connection_count == 1:
                first_publish_received.set_result(publish)
                await writer.close()
                return

            retry_publish_received.set_result(publish)
            assert publish.packet_id is not None
            await PubackPacket.build(publish.packet_id).to_stream(writer)
            with suppress(Exception):
                await asyncio.wait_for(DisconnectPacket.from_stream(reader), timeout=2)
            await writer.close()
        except Exception as exc:
            if not server_error.done():
                server_error.set_exception(exc)

    server = await asyncio.start_server(fake_broker, "127.0.0.1", 0)
    client = MQTTClient(client_id="client-qos1-no-puback", config={"auto_reconnect": False})
    publish_task: asyncio.Task[OutgoingApplicationMessage] | None = None
    reconnect_task: asyncio.Task[int] | None = None

    try:
        assert await client.connect(f"mqtt://127.0.0.1:{server_port(server)}/", cleansession=False) == 0
        publish_task = asyncio.create_task(client.publish(topic, payload, QOS_1))

        first_publish = await wait_for_fake_broker_result(first_publish_received, server_error, "initial QoS1 PUBLISH")
        assert first_publish.topic_name == topic
        assert first_publish.data == payload
        assert first_publish.qos == QOS_1
        assert first_publish.dup_flag is False
        assert first_publish.packet_id is not None

        await wait_for_client_state(client, "disconnected")
        assert client.session is not None
        assert client.session.inflight_out_count == 1
        with suppress(asyncio.CancelledError):
            await publish_task

        reconnect_task = asyncio.create_task(client.reconnect(cleansession=False))
        retry_publish = await wait_for_fake_broker_result(retry_publish_received, server_error, "retried QoS1 PUBLISH")
        assert retry_publish.topic_name == topic
        assert retry_publish.data == payload
        assert retry_publish.qos == QOS_1
        assert retry_publish.dup_flag is True
        assert retry_publish.packet_id == first_publish.packet_id
        assert await asyncio.wait_for(reconnect_task, timeout=2) == 0
    finally:
        for task in (publish_task, reconnect_task):
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        with suppress(Exception):
            await client.disconnect()
        for writer in server_writers:
            await writer.close()
        server.close()
        await server.wait_closed()
        if server_error.done():
            server_error.result()


@pytest.mark.asyncio
async def test_client_qos2_reconnect_while_waiting_for_pubrec_republishes() -> None:
    topic = "/client/qos2/no-pubrec/reconnect"
    payload = b"client qos2 pubrec resend payload"
    loop = asyncio.get_running_loop()
    first_publish_received: asyncio.Future[PublishPacket] = loop.create_future()
    retry_publish_received: asyncio.Future[PublishPacket] = loop.create_future()
    retry_pubrel_received: asyncio.Future[PubrelPacket] = loop.create_future()
    server_error: asyncio.Future[None] = loop.create_future()
    server_writers: list[StreamWriterAdapter] = []
    connection_count = 0

    async def fake_broker(raw_reader: asyncio.StreamReader, raw_writer: asyncio.StreamWriter) -> None:
        nonlocal connection_count
        reader, writer = StreamReaderAdapter(raw_reader), StreamWriterAdapter(raw_writer)
        server_writers.append(writer)
        connection_count += 1

        try:
            await ConnectPacket.from_stream(reader)
            await ConnackPacket.build(session_parent=1 if connection_count > 1 else 0, return_code=0).to_stream(writer)

            publish = await asyncio.wait_for(PublishPacket.from_stream(reader), timeout=2)
            if connection_count == 1:
                first_publish_received.set_result(publish)
                await writer.close()
                return

            retry_publish_received.set_result(publish)
            assert publish.packet_id is not None
            await PubrecPacket.build(publish.packet_id).to_stream(writer)
            pubrel = await asyncio.wait_for(PubrelPacket.from_stream(reader), timeout=2)
            retry_pubrel_received.set_result(pubrel)
            await PubcompPacket.build(pubrel.packet_id).to_stream(writer)
            with suppress(Exception):
                await asyncio.wait_for(DisconnectPacket.from_stream(reader), timeout=2)
            await writer.close()
        except Exception as exc:
            if not server_error.done():
                server_error.set_exception(exc)

    server = await asyncio.start_server(fake_broker, "127.0.0.1", 0)
    client = MQTTClient(client_id="client-qos2-no-pubrec", config={"auto_reconnect": False})
    publish_task: asyncio.Task[OutgoingApplicationMessage] | None = None
    reconnect_task: asyncio.Task[int] | None = None

    try:
        assert await client.connect(f"mqtt://127.0.0.1:{server_port(server)}/", cleansession=False) == 0
        publish_task = asyncio.create_task(client.publish(topic, payload, QOS_2))

        first_publish = await wait_for_fake_broker_result(first_publish_received, server_error, "initial QoS2 PUBLISH")
        assert first_publish.topic_name == topic
        assert first_publish.data == payload
        assert first_publish.qos == QOS_2
        assert first_publish.dup_flag is False
        assert first_publish.packet_id is not None

        await wait_for_client_state(client, "disconnected")
        assert client.session is not None
        assert client.session.inflight_out_count == 1
        with suppress(asyncio.CancelledError):
            await publish_task

        reconnect_task = asyncio.create_task(client.reconnect(cleansession=False))
        retry_publish = await wait_for_fake_broker_result(retry_publish_received, server_error, "retried QoS2 PUBLISH")
        assert retry_publish.topic_name == topic
        assert retry_publish.data == payload
        assert retry_publish.qos == QOS_2
        assert retry_publish.dup_flag is True
        assert retry_publish.packet_id == first_publish.packet_id

        retry_pubrel = await wait_for_fake_broker_result(retry_pubrel_received, server_error, "retried QoS2 PUBREL")
        assert retry_pubrel.packet_id == first_publish.packet_id
        assert await asyncio.wait_for(reconnect_task, timeout=2) == 0
    finally:
        for task in (publish_task, reconnect_task):
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        with suppress(Exception):
            await client.disconnect()
        for writer in server_writers:
            await writer.close()
        server.close()
        await server.wait_closed()
        if server_error.done():
            server_error.result()


@pytest.mark.asyncio
async def test_client_qos2_reconnect_while_waiting_for_pubcomp_resends_pubrel() -> None:
    topic = "/client/qos2/no-pubcomp/reconnect"
    payload = b"client qos2 pubcomp resend payload"
    loop = asyncio.get_running_loop()
    first_publish_received: asyncio.Future[PublishPacket] = loop.create_future()
    first_pubrel_received: asyncio.Future[PubrelPacket] = loop.create_future()
    retry_pubrel_received: asyncio.Future[PubrelPacket] = loop.create_future()
    server_error: asyncio.Future[None] = loop.create_future()
    server_writers: list[StreamWriterAdapter] = []
    connection_count = 0

    async def fake_broker(raw_reader: asyncio.StreamReader, raw_writer: asyncio.StreamWriter) -> None:
        nonlocal connection_count
        reader, writer = StreamReaderAdapter(raw_reader), StreamWriterAdapter(raw_writer)
        server_writers.append(writer)
        connection_count += 1

        try:
            await ConnectPacket.from_stream(reader)
            await ConnackPacket.build(session_parent=1 if connection_count > 1 else 0, return_code=0).to_stream(writer)

            if connection_count == 1:
                publish = await asyncio.wait_for(PublishPacket.from_stream(reader), timeout=2)
                first_publish_received.set_result(publish)
                assert publish.packet_id is not None
                await PubrecPacket.build(publish.packet_id).to_stream(writer)
                pubrel = await asyncio.wait_for(PubrelPacket.from_stream(reader), timeout=2)
                first_pubrel_received.set_result(pubrel)
                await writer.close()
                return

            pubrel = await asyncio.wait_for(PubrelPacket.from_stream(reader), timeout=2)
            retry_pubrel_received.set_result(pubrel)
            await PubcompPacket.build(pubrel.packet_id).to_stream(writer)
            with suppress(Exception):
                await asyncio.wait_for(DisconnectPacket.from_stream(reader), timeout=2)
            await writer.close()
        except Exception as exc:
            if not server_error.done():
                server_error.set_exception(exc)

    server = await asyncio.start_server(fake_broker, "127.0.0.1", 0)
    client = MQTTClient(client_id="client-qos2-no-pubcomp", config={"auto_reconnect": False})
    publish_task: asyncio.Task[OutgoingApplicationMessage] | None = None
    reconnect_task: asyncio.Task[int] | None = None

    try:
        assert await client.connect(f"mqtt://127.0.0.1:{server_port(server)}/", cleansession=False) == 0
        publish_task = asyncio.create_task(client.publish(topic, payload, QOS_2))

        first_publish = await wait_for_fake_broker_result(first_publish_received, server_error, "initial QoS2 PUBLISH")
        assert first_publish.topic_name == topic
        assert first_publish.data == payload
        assert first_publish.qos == QOS_2
        assert first_publish.dup_flag is False
        assert first_publish.packet_id is not None

        first_pubrel = await wait_for_fake_broker_result(first_pubrel_received, server_error, "initial QoS2 PUBREL")
        assert first_pubrel.packet_id == first_publish.packet_id

        await wait_for_client_state(client, "disconnected")
        assert client.session is not None
        assert client.session.inflight_out_count == 1
        with suppress(asyncio.CancelledError):
            await publish_task

        reconnect_task = asyncio.create_task(client.reconnect(cleansession=False))
        retry_pubrel = await wait_for_fake_broker_result(retry_pubrel_received, server_error, "retried QoS2 PUBREL")
        assert retry_pubrel.packet_id == first_publish.packet_id
        assert await asyncio.wait_for(reconnect_task, timeout=2) == 0
    finally:
        for task in (publish_task, reconnect_task):
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        with suppress(Exception):
            await client.disconnect()
        for writer in server_writers:
            await writer.close()
        server.close()
        await server.wait_closed()
        if server_error.done():
            server_error.result()


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
