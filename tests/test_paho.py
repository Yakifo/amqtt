import asyncio
import logging
import random
from unittest.mock import MagicMock, call, patch

import pytest
from paho.mqtt import client as mqtt_client

from amqtt.broker import BrokerEvents
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2

logger = logging.getLogger(__name__)
paho_logger = logging.getLogger("paho_client")


# monkey patch MagicMock
# taken from https://stackoverflow.com/questions/51394411/python-object-magicmock-cant-be-used-in-await-expression
async def async_magic():
    pass


MagicMock.__await__ = lambda _: async_magic().__await__()

@pytest.mark.asyncio
async def test_paho_connect(broker, mock_plugin_manager):

    test_complete = asyncio.Event()

    host = "localhost"
    port = 1883
    client_id = f'python-mqtt-{random.randint(0, 1000)}'

    def on_connect(client, userdata, flags, rc, properties=None):
        assert rc == 0, f"Connection failed with result code {rc}"
        client.disconnect()

    def on_disconnect(client, userdata, flags, rc, properties=None):
        assert rc == 0, f"Disconnect failed with result code {rc}"
        test_complete.set()

    test_client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, client_id=client_id)
    test_client.enable_logger(paho_logger)

    test_client.on_connect = on_connect
    test_client.on_disconnect = on_disconnect

    test_client.connect(host, port)
    test_client.loop_start()

    await asyncio.wait_for(test_complete.wait(), timeout=5)
    await asyncio.sleep(0.1)
    broker.plugins_manager.assert_has_calls(
        [
            call.fire_event(
                BrokerEvents.CLIENT_CONNECTED,
                client_id=client_id,
            ),
            call.fire_event(
                BrokerEvents.CLIENT_DISCONNECTED,
                client_id=client_id,
            ),
        ],
        any_order=True,
    )
    test_client.loop_stop()


@pytest.mark.asyncio
async def test_paho_qos1(broker, mock_plugin_manager):

    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    ret = await sub_client.subscribe(
        [("/qos1", QOS_1),],
    )

    host = "localhost"
    port = 1883
    client_id = f'python-mqtt-{random.randint(0, 1000)}'

    test_client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, client_id=client_id)
    test_client.enable_logger(paho_logger)

    test_client.connect(host, port)
    test_client.loop_start()
    await asyncio.sleep(0.1)
    test_client.publish("/qos1", "test message", qos=1)
    await asyncio.sleep(0.1)
    test_client.loop_stop()

    message = await sub_client.deliver_message()
    assert message is not None
    assert message.qos == 1
    assert message.topic == "/qos1"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_paho_qos2(broker, mock_plugin_manager):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    ret = await sub_client.subscribe(
        [("/qos2", QOS_2), ],
    )

    host = "localhost"
    port = 1883
    client_id = f'python-mqtt-{random.randint(0, 1000)}'

    test_client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, client_id=client_id)
    test_client.enable_logger(paho_logger)

    test_client.connect(host, port)
    test_client.loop_start()
    await asyncio.sleep(0.1)
    test_client.publish("/qos2", "test message", qos=2)
    await asyncio.sleep(0.1)
    test_client.loop_stop()

    message = await sub_client.deliver_message()
    assert message is not None
    assert message.qos == 2
    assert message.topic == "/qos2"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)
