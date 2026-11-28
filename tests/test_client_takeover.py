"""Client-id takeover through real loopback MQTT connections (issue #429)."""

import asyncio
import struct
from unittest.mock import AsyncMock

import pytest

from amqtt.broker import Broker


def mqtt_string(value):
    value = value.encode() if isinstance(value, str) else value
    return struct.pack('!H', len(value)) + value


async def packet(reader):
    header = (await asyncio.wait_for(reader.readexactly(1), 2))[0]
    length = 0
    multiplier = 1
    while True:
        digit = (await asyncio.wait_for(reader.readexactly(1), 2))[0]
        length += (digit & 127) * multiplier
        if not digit & 128:
            break
        multiplier *= 128
    return header, await asyncio.wait_for(reader.readexactly(length), 2)


async def send(writer, header, payload=b''):
    assert len(payload) < 128
    writer.write(bytes([header, len(payload)]) + payload)
    await writer.drain()


@pytest.fixture
async def takeover_broker():
    broker = Broker({
        'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1:0'}},
        'plugins': {'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': True}},
    })
    await broker.start()
    port = broker._servers['default'].instance.sockets[0].getsockname()[1]
    connections = []

    async def connect(client_id, clean, will=None, accepted=True, will_retain=False):
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        connections.append(writer)
        flags = (2 if clean else 0) | (4 if will else 0) | (32 if will_retain else 0)
        payload = b'\x00\x04MQTT\x04' + bytes([flags]) + b'\x00\x3c' + mqtt_string(client_id)
        if will:
            payload += mqtt_string('wills') + mqtt_string(will)
        await send(writer, 0x10, payload)
        header, payload = await packet(reader)
        assert header == 0x20 and payload[1] == (0 if accepted else 5)
        return reader, writer, payload[0]

    yield broker, connect

    for writer in connections:
        writer.close()
        await writer.wait_closed()
    await broker.shutdown()


@pytest.mark.parametrize('first_clean', [False, True])
@pytest.mark.parametrize('second_clean', [False, True])
async def test_client_id_takeover(takeover_broker, first_clean, second_clean):
    broker, connect = takeover_broker
    old_reader, old_writer, _ = await connect('sensor', first_clean)
    await send(old_writer, 0x82, b'\x00\x01' + mqtt_string('readings') + b'\x00')
    assert await packet(old_reader) == (0x90, b'\x00\x01\x00')

    new_reader, new_writer, present = await connect('sensor', second_clean)
    assert present == int(not first_clean and not second_clean)
    # A round trip proves that the replacement survives the old handler's cleanup.
    await send(new_writer, 0xc0)
    assert await packet(new_reader) == (0xd0, b'')
    assert await asyncio.wait_for(old_reader.read(1), 2) == b''

    if not first_clean and not second_clean:
        await broker.internal_message_broadcast('readings', b'resumed')
        assert await packet(new_reader) == (0x30, mqtt_string('readings') + b'resumed')
    else:
        assert 'readings' not in broker.subscriptions

    await send(new_writer, 0x82, b'\x00\x02' + mqtt_string('readings') + b'\x00')
    assert await packet(new_reader) == (0x90, b'\x00\x02\x00')
    await broker.internal_message_broadcast('readings', b'12.6')
    assert await packet(new_reader) == (0x30, mqtt_string('readings') + b'12.6')
    await send(new_writer, 0xe0)


async def test_takeover_preserves_each_connections_will(takeover_broker):
    broker, connect = takeover_broker
    observer, writer, _ = await connect('observer', True)
    await send(writer, 0x82, b'\x00\x01' + mqtt_string('wills') + b'\x00')
    assert await packet(observer) == (0x90, b'\x00\x01\x00')
    old_reader, _, _ = await connect('sensor', False, will=b'old')
    new_reader, new_writer, _ = await connect('sensor', False, will=b'new', will_retain=True)
    assert await packet(observer) == (0x30, mqtt_string('wills') + b'old')
    assert await asyncio.wait_for(old_reader.read(1), 2) == b''
    await send(new_writer, 0xc0)
    assert await packet(new_reader) == (0xd0, b'')
    new_writer.close()
    await new_writer.wait_closed()
    assert await packet(observer) == (0x30, mqtt_string('wills') + b'new')
    assert broker.retained_messages['wills'].data == b'new'
    await send(writer, 0xe0)


@pytest.mark.parametrize('clean', [False, True])
async def test_rejected_reconnect_leaves_live_connection(takeover_broker, monkeypatch, clean):
    broker, connect = takeover_broker
    reader, writer, _ = await connect('sensor', False)
    monkeypatch.setattr(broker, '_authenticate', AsyncMock(return_value=False))
    rejected, _, _ = await connect('sensor', clean, accepted=False)
    assert await asyncio.wait_for(rejected.read(1), 2) == b''
    await send(writer, 0xc0)
    assert await packet(reader) == (0xd0, b'')
    assert broker.sessions['sensor'][0].transitions.is_connected()
    await send(writer, 0xe0)


@pytest.mark.parametrize('clean', [False, True])
async def test_simultaneous_takeovers_leave_one_live_connection(takeover_broker, clean):
    broker, connect = takeover_broker
    clients = await asyncio.gather(*(connect('sensor', clean) for _ in range(3)))
    active_handler = broker.sessions['sensor'][1]
    active_port = active_handler.writer.get_peer_info()[1]
    for reader, writer, _ in clients:
        if writer.get_extra_info('sockname')[1] == active_port:
            await send(writer, 0xc0)
            assert await packet(reader) == (0xd0, b'')
            await send(writer, 0xe0)
        else:
            assert await asyncio.wait_for(reader.read(1), 2) == b''
