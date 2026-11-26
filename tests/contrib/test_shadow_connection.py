import asyncio
import json

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0


@pytest.mark.asyncio
async def test_repeated_shadow_requests_keep_connection_processing(tmp_path):
    broker = Broker({
        'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1:0'}},
        'plugins': {
            'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': True},
            'amqtt.contrib.shadows.ShadowPlugin': {
                'connection': f'sqlite+aiosqlite:///{tmp_path / "shadows.db"}'},
        },
    })
    await broker.start()
    port = broker._servers['default'].instance.sockets[0].getsockname()[1]
    client = MQTTClient(client_id='sensor', config={'auto_reconnect': False})
    try:
        await client.connect(f'mqtt://127.0.0.1:{port}')
        assert await client.subscribe([
            ('$shadow/sensor/battery/update/accepted', QOS_0),
            ('$shadow/sensor/battery/get/accepted', QOS_0),
            ('normal', QOS_0),
        ]) == [QOS_0] * 3
        for voltage in (12.5, 12.8):
            await client.publish('$shadow/sensor/battery/update',
                                 json.dumps({'state': {'reported': {'voltage': voltage}}}).encode(), QOS_0)
            reply = await asyncio.wait_for(client.deliver_message(), 2)
            assert reply.topic == '$shadow/sensor/battery/update/accepted'
            assert json.loads(reply.data)['state']['reported']['voltage'] == voltage
            await client.publish('$shadow/sensor/battery/get', b'', QOS_0)
            reply = await asyncio.wait_for(client.deliver_message(), 2)
            assert reply.topic == '$shadow/sensor/battery/get/accepted'
            assert json.loads(reply.data)['state']['reported']['voltage'] == voltage
        await client.publish('normal', b'still connected', QOS_0)
        reply = await asyncio.wait_for(client.deliver_message(), 2)
        assert (reply.topic, reply.data) == ('normal', b'still connected')
    finally:
        await client.disconnect()
        await broker.shutdown()
