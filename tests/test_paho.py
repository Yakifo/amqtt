import asyncio
import logging
import random
import threading
import time
from pathlib import Path
from threading import Thread
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
import yaml
from paho.mqtt import client as paho_client
from yaml import Loader

from amqtt.broker import Broker
from amqtt.events import BrokerEvents
from amqtt.client import MQTTClient
from amqtt.mqtt3.constants import QOS_1, QOS_2
from amqtt.session import Session

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

    test_client = paho_client.Client(paho_client.CallbackAPIVersion.VERSION2, client_id=client_id)
    test_client.enable_logger(paho_logger)

    test_client.on_connect = on_connect
    test_client.on_disconnect = on_disconnect

    test_client.connect(host, port)
    test_client.loop_start()

    await asyncio.wait_for(test_complete.wait(), timeout=5)
    await asyncio.sleep(0.1)

    broker.plugins_manager.fire_event.assert_called()
    assert broker.plugins_manager.fire_event.call_count > 2

    # double indexing is ugly, but call_args_list returns a tuple of tuples
    events = [c[0][0] for c in broker.plugins_manager.fire_event.call_args_list]
    assert BrokerEvents.CLIENT_CONNECTED in events
    assert BrokerEvents.CLIENT_DISCONNECTED in events

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

    test_client = paho_client.Client(paho_client.CallbackAPIVersion.VERSION2, client_id=client_id)
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

    test_client = paho_client.Client(paho_client.CallbackAPIVersion.VERSION2, client_id=client_id)
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



def run_paho_client(flag):
    client_id = 'websocket_client_1'
    logging.info("creating paho client")
    test_client = paho_client.Client(callback_api_version=paho_client.CallbackAPIVersion.VERSION2,
                                     transport='websockets',
                                     client_id=client_id)

    test_client.ws_set_options('')
    logging.info("client connecting...")
    test_client.connect('127.0.0.1', 8080)
    logging.info("starting loop")
    test_client.loop_start()
    logging.info("client connected")
    time.sleep(1)
    logging.info("sending messages")
    test_client.publish("/qos2", "test message", qos=2)
    test_client.publish("/qos2", "test message", qos=2)
    test_client.publish("/qos2", "test message", qos=2)
    test_client.publish("/qos2", "test message", qos=2)
    time.sleep(1)
    test_client.loop_stop()
    test_client.disconnect()
    flag.set()


@pytest.mark.asyncio
async def test_paho_ws():
    path = Path('docs_test/test.amqtt.local.yaml')
    with path.open() as f:
        cfg: dict[str, Any] = yaml.load(f, Loader=Loader)
    logger.warning(cfg)
    broker = Broker(config=cfg)
    await broker.start()

    # python websockets and paho mqtt don't play well with each other in the same thread
    flag = threading.Event()
    thread = Thread(target=run_paho_client, args=(flag,))
    thread.start()

    await asyncio.sleep(5)
    thread.join(1)

    assert flag.is_set(), "paho thread didn't execute completely"

    logging.info("client disconnected")
    await broker.shutdown()
