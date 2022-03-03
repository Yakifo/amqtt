# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import asyncio
import os
import logging
import urllib.request
import tempfile
import shutil

import pytest

from amqtt.client import MQTTClient, ConnectException
from amqtt.broker import Broker
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

formatter = (
    "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
)
logging.basicConfig(level=logging.ERROR, format=formatter)
log = logging.getLogger(__name__)

broker_config = {
    "listeners": {
        "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        "ws": {"type": "ws", "bind": "127.0.0.1:8080", "max_connections": 10},
        "wss": {"type": "ws", "bind": "127.0.0.1:8081", "max_connections": 10},
    },
    "sys_interval": 0,
    "auth": {
        "allow-anonymous": True,
    },
}

ca_file: str = ""
temp_dir: str = ""


def setup_module():
    global ca_file, temp_dir

    temp_dir = tempfile.mkdtemp(prefix="amqtt-test-")
    url = "http://test.mosquitto.org/ssl/mosquitto.org.crt"
    ca_file = os.path.join(temp_dir, "mosquitto.org.crt")
    urllib.request.urlretrieve(url, ca_file)
    log.info("stored mosquitto cert at %s" % ca_file)


def teardown_module():
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_connect_tcp():
    client = MQTTClient()
    await client.connect("mqtt://test.mosquitto.org/")
    assert client.session is not None
    await client.disconnect()


@pytest.mark.asyncio
async def test_connect_tcp_secure():
    client = MQTTClient(config={"check_hostname": False})
    await client.connect("mqtts://test.mosquitto.org/", cafile=ca_file)
    assert client.session is not None
    await client.disconnect()


@pytest.mark.asyncio
async def test_connect_tcp_failure():
    config = {"auto_reconnect": False}
    client = MQTTClient(config=config)
    with pytest.raises(ConnectException):
        await client.connect("mqtt://127.0.0.1/")


@pytest.mark.asyncio
async def test_connect_ws():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("ws://127.0.0.1:8080/")
    assert client.session is not None
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_reconnect_ws_retain_username_password():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("ws://fred:password@127.0.0.1:8080/")
    assert client.session is not None
    await client.disconnect()
    await client.reconnect()

    assert client.session.username is not None
    assert client.session.password is not None
    await broker.shutdown()


@pytest.mark.asyncio
async def test_connect_ws_secure():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("ws://127.0.0.1:8081/", cafile=ca_file)
    assert client.session is not None
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_connect_username_without_password():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("mqtt://alice@127.0.0.1/")
    assert client.session is not None
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_ping():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    await client.ping()
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_subscribe():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("$SYS/broker/uptime", QOS_0),
            ("$SYS/broker/uptime", QOS_1),
            ("$SYS/broker/uptime", QOS_2),
        ]
    )
    assert ret[0] == QOS_0
    assert ret[1] == QOS_1
    assert ret[2] == QOS_2
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_unsubscribe():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("$SYS/broker/uptime", QOS_0),
        ]
    )
    assert ret[0] == QOS_0
    await client.unsubscribe(["$SYS/broker/uptime"])
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_deliver():
    data = b"data"
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("test_topic", QOS_0),
        ]
    )
    assert ret[0] == QOS_0
    client_pub = MQTTClient()
    await client_pub.connect("mqtt://127.0.0.1/")
    await client_pub.publish("test_topic", data, QOS_0)
    await client_pub.disconnect()
    message = await client.deliver_message()
    assert message is not None
    assert message.publish_packet is not None
    assert message.data == data
    await client.unsubscribe(["$SYS/broker/uptime"])
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_deliver_timeout():
    broker = Broker(broker_config, plugin_namespace="amqtt.test.plugins")
    await broker.start()
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("test_topic", QOS_0),
        ]
    )
    assert ret[0] == QOS_0
    with pytest.raises(asyncio.TimeoutError):
        await client.deliver_message(timeout=2)
    await client.unsubscribe(["$SYS/broker/uptime"])
    await client.disconnect()
    await broker.shutdown()
