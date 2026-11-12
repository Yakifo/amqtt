"""Regression tests for previously encountered bugs."""

import asyncio

import pytest

from amqtt.adapters import StreamReaderAdapter, StreamWriterAdapter
from amqtt.client import MQTTClient
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket, ConnectPayload, ConnectVariableHeader


@pytest.mark.asyncio
async def test_client_configured_keep_alive_is_received_by_broker(broker_fixture):
    client_id = "keep-alive-client"
    keep_alive = 30
    client = MQTTClient(
        client_id=client_id,
        config={"auto_reconnect": False, "keep_alive": keep_alive},
    )

    await client.connect("mqtt://127.0.0.1/")

    broker_session, _ = broker_fixture._sessions[client_id]
    broker_keep_alive = broker_session.keep_alive
    await client.disconnect()

    assert broker_keep_alive == keep_alive


@pytest.mark.asyncio
async def test_broker_disconnects_client_after_keep_alive_timeout(broker_fixture):
    keep_alive = 1
    conn_reader, conn_writer = await asyncio.open_connection("127.0.0.1", 1883)
    reader = StreamReaderAdapter(conn_reader)
    writer = StreamWriterAdapter(conn_writer)

    variable_header = ConnectVariableHeader()
    variable_header.keep_alive = keep_alive
    variable_header.clean_session_flag = True
    payload = ConnectPayload()
    payload.client_id = "inactive-client"

    try:
        await ConnectPacket(variable_header=variable_header, payload=payload).to_stream(writer)
        connack = await ConnackPacket.from_stream(reader)
        assert connack.return_code == 0
        assert payload.client_id in broker_fixture._sessions

        disconnect_timeout = keep_alive * 1.5 + 1
        assert await asyncio.wait_for(conn_reader.read(1), timeout=disconnect_timeout) == b""
    finally:
        conn_writer.close()
        await conn_writer.wait_closed()
