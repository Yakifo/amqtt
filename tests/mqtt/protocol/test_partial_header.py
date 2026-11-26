import asyncio

import pytest

from amqtt.adapters import BufferWriter, StreamReaderAdapter
from amqtt.mqtt.constants import QOS_0
from amqtt.mqtt.protocol.client_handler import ClientProtocolHandler
from amqtt.mqtt.publish import PublishPacket
from amqtt.session import Session
from tests.mqtt.protocol.test_client_handler import DummyPluginManager


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix_length", [0, 1, 2])
async def test_header_read_survives_idle_timeouts(prefix_length):
    """Keep-alive checks must not consume a partial fixed header twice."""
    stream = asyncio.StreamReader()
    session = Session()
    session.client_id = "fragmented-header"
    handler = ClientProtocolHandler(DummyPluginManager())
    handler.attach(session, StreamReaderAdapter(stream), BufferWriter())
    handler._keepalive_timeout = 0.01
    timed_out = asyncio.Event()
    timeout_count = 0

    def on_timeout():
        nonlocal timeout_count
        timeout_count += 1
        if timeout_count >= 2:
            timed_out.set()

    handler.handle_read_timeout = on_timeout
    packet = PublishPacket.build("sensor/voltage", b"x" * 150, None, False, QOS_0, False).to_bytes()
    stream.feed_data(packet[:prefix_length])
    await handler.start()
    try:
        await asyncio.wait_for(timed_out.wait(), 1)
        stream.feed_data(packet[prefix_length:])
        message = await asyncio.wait_for(handler.mqtt_deliver_next_message(), 1)
        assert message is not None
        assert message.topic == "sensor/voltage"
        assert message.data == b"x" * 150
    finally:
        await handler.stop()
