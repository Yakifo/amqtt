import asyncio
import logging
from importlib.metadata import EntryPoint
from unittest.mock import patch

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.errors import ClientError, ConnectError
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.ERROR, format=formatter)
log = logging.getLogger(__name__)


# @pytest.mark.asyncio
# async def test_connect_tcp():
#     client = MQTTClient()
#     await client.connect("mqtt://test.mosquitto.org:1883/")
#     assert client.session is not None
#     await client.disconnect()


# @pytest.mark.asyncio
# async def test_connect_tcp_secure(ca_file_fixture):
#     client = MQTTClient(config={"check_hostname": False})
#     await client.connect("mqtts://test.mosquitto.org:8883/", cafile=ca_file_fixture)
#     assert client.session is not None
#     await client.disconnect()


@pytest.mark.asyncio
async def test_connect_tcp_failure():
    config = {"auto_reconnect": False}
    client = MQTTClient(config=config)
    with pytest.raises(ConnectError):
        await client.connect("mqtt://127.0.0.1/")


@pytest.mark.asyncio
async def test_connect_ws(broker_fixture):
    client = MQTTClient()
    await client.connect("ws://127.0.0.1:8080/")
    assert client.session is not None
    await client.disconnect()


@pytest.mark.asyncio
async def test_reconnect_ws_retain_username_password(broker_fixture):
    client = MQTTClient()
    await client.connect("ws://fred:password@127.0.0.1:8080/")
    assert client.session is not None
    await client.disconnect()
    await client.reconnect()

    assert client.session.username is not None
    assert client.session.password is not None


@pytest.mark.asyncio
async def test_connect_ws_secure(ca_file_fixture, broker_fixture):
    client = MQTTClient()
    await client.connect("ws://127.0.0.1:8081/", cafile=ca_file_fixture)
    assert client.session is not None
    await client.disconnect()


@pytest.mark.asyncio
async def test_connect_username_without_password(broker_fixture):
    client = MQTTClient()
    await client.connect("mqtt://alice@127.0.0.1/")
    assert client.session is not None
    await client.disconnect()


@pytest.mark.asyncio
async def test_ping(broker_fixture):
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    await client.ping()
    await client.disconnect()


@pytest.mark.asyncio
async def test_subscribe(broker_fixture):
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("$SYS/broker/uptime", QOS_0),
            ("$SYS/broker/uptime", QOS_1),
            ("$SYS/broker/uptime", QOS_2),
        ],
    )
    assert ret[0] == QOS_0
    assert ret[1] == QOS_1
    assert ret[2] == QOS_2
    await client.disconnect()


@pytest.mark.asyncio
async def test_unsubscribe(broker_fixture):
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("$SYS/broker/uptime", QOS_0),
        ],
    )
    assert ret[0] == QOS_0
    await client.unsubscribe(["$SYS/broker/uptime"])
    await client.disconnect()


@pytest.mark.asyncio
async def test_deliver(broker_fixture):
    data = b"data"
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("test_topic", QOS_0),
        ],
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


@pytest.mark.asyncio
async def test_deliver_timeout(broker_fixture):
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1/")
    assert client.session is not None
    ret = await client.subscribe(
        [
            ("test_topic", QOS_0),
        ],
    )
    assert ret[0] == QOS_0
    with pytest.raises(asyncio.TimeoutError):
        await client.deliver_message(timeout_duration=2)
    await client.unsubscribe(["$SYS/broker/uptime"])
    await client.disconnect()


@pytest.mark.asyncio
async def test_cancel_publish_qos1(broker_fixture):
    """Tests that timeouts on published messages will clean up in-flight messages."""
    data = b"data"
    client_pub = MQTTClient()
    await client_pub.connect("mqtt://127.0.0.1/")

    assert client_pub.session is not None
    assert client_pub._handler is not None

    assert client_pub.session.inflight_out_count == 0
    fut = asyncio.create_task(client_pub.publish("test_topic", data, QOS_1))
    assert len(client_pub._handler._puback_waiters) == 0
    while len(client_pub._handler._puback_waiters) == 0 and not fut.done():
        await asyncio.sleep(0)
    assert len(client_pub._handler._puback_waiters) == 1
    assert client_pub.session.inflight_out_count == 1
    fut.cancel()
    await asyncio.wait([fut])
    assert len(client_pub._handler._puback_waiters) == 0
    assert client_pub.session.inflight_out_count == 0

    await asyncio.sleep(0.1)
    await client_pub.disconnect()


@pytest.mark.asyncio
async def test_cancel_publish_qos2_pubrec(broker_fixture):
    """Tests that timeouts on published messages will clean up in-flight messages."""
    data = b"data"
    client_pub = MQTTClient()
    await client_pub.connect("mqtt://127.0.0.1/")

    assert client_pub.session is not None
    assert client_pub._handler is not None

    assert client_pub.session.inflight_out_count == 0
    fut = asyncio.create_task(client_pub.publish("test_topic", data, QOS_2))
    assert len(client_pub._handler._pubrec_waiters) == 0
    while len(client_pub._handler._pubrec_waiters) == 0 or fut.done() or fut.cancelled():
        await asyncio.sleep(0)
    assert len(client_pub._handler._pubrec_waiters) == 1
    assert client_pub.session.inflight_out_count == 1
    fut.cancel()
    await asyncio.sleep(1)
    await asyncio.wait([fut])
    assert len(client_pub._handler._pubrec_waiters) == 0
    assert client_pub.session.inflight_out_count == 0

    await asyncio.sleep(0.1)
    await client_pub.disconnect()


@pytest.mark.asyncio
async def test_cancel_publish_qos2_pubcomp(broker_fixture):
    """Tests that timeouts on published messages will clean up in-flight messages."""
    data = b"data"
    client_pub = MQTTClient()
    await client_pub.connect("mqtt://127.0.0.1/")

    assert client_pub.session is not None
    assert client_pub._handler is not None

    assert client_pub.session.inflight_out_count == 0
    fut = asyncio.create_task(client_pub.publish("test_topic", data, QOS_2))
    assert len(client_pub._handler._pubcomp_waiters) == 0
    while len(client_pub._handler._pubcomp_waiters) == 0 and not fut.done():
        await asyncio.sleep(0)
    assert len(client_pub._handler._pubcomp_waiters) == 1
    fut.cancel()
    await asyncio.wait([fut])
    assert len(client_pub._handler._pubcomp_waiters) == 0
    assert client_pub.session.inflight_out_count == 0

    await asyncio.sleep(0.1)
    await client_pub.disconnect()


@pytest.fixture
def client_config():
    return {
        "default_retain": False,
        "topics": {
                "test": {
                    "qos": 0
                },
                "some_topic": {
                    "retain": True,
                    "qos": 2
                }
        },
        "keep_alive": 10,
        "broker": {
            "uri": "mqtt://localhost:1884"
        },
        "reconnect_max_interval": 5,
        "will": {
            "topic": "test/will/topic",
            "retain": True,
            "message": "client ABC has disconnected",
            "qos": 1
        },
        "ping_delay": 1,
        "default_qos": 0,
        "auto_reconnect": True,
        "reconnect_retries": 10
    }


@pytest.mark.asyncio
async def test_client_will_with_clean_disconnect(broker_fixture):
    config = {
        "will": {
            "topic": "test/will/topic",
            "retain": False,
            "message": "client ABC has disconnected",
            "qos": 1
        },
    }

    client1 = MQTTClient(client_id="client1", config=config)
    await client1.connect("mqtt://localhost:1883")

    client2 = MQTTClient(client_id="client2")
    await client2.connect("mqtt://localhost:1883")
    await client2.subscribe(
        [
            ("test/will/topic", QOS_0),
        ]
    )

    await client1.disconnect()
    await asyncio.sleep(1)

    with pytest.raises(asyncio.TimeoutError):
        message = await client2.deliver_message(timeout_duration=2)
        # if we do get a message, make sure it's not a will message
        assert message.topic != "test/will/topic"

    await client2.disconnect()


@pytest.mark.asyncio
async def test_client_will_with_abrupt_disconnect(broker_fixture):
    config = {
        "will": {
            "topic": "test/will/topic",
            "retain": False,
            "message": "client ABC has disconnected",
            "qos": 1
        },
    }

    client1 = MQTTClient(client_id="client1", config=config)
    await client1.connect("mqtt://localhost:1883")

    client2 = MQTTClient(client_id="client2")
    await client2.connect("mqtt://localhost:1883")
    await client2.subscribe(
        [
            ("test/will/topic", QOS_0),
        ]
    )

    # instead of client.disconnect, call the necessary closing but without sending the disconnect packet
    await client1.cancel_tasks()
    if client1._disconnect_task and not client1._disconnect_task.done():
        client1._disconnect_task.cancel()
    client1._connected_state.clear()
    await client1._handler.stop()
    client1.session.transitions.disconnect()

    await asyncio.sleep(1)


    message = await client2.deliver_message(timeout_duration=1)
    # make sure we receive the will message
    assert message.topic == "test/will/topic"
    assert message.data == b'client ABC has disconnected'

    await client2.disconnect()


@pytest.mark.asyncio
async def test_client_retained_will_with_abrupt_disconnect(broker_fixture):

    # verifying client functionality of retained will topic/message

    config = {
        "will": {
            "topic": "test/will/topic",
            "retain": True,
            "message": "client ABC has disconnected",
            "qos": 1
        },
    }

    # first client, connect with retained will message
    client1 = MQTTClient(client_id="client1", config=config)
    await client1.connect('mqtt://localhost:1883')

    client2 = MQTTClient(client_id="client2")
    await client2.connect('mqtt://localhost:1883')
    await  client2.subscribe([
        ("test/will/topic", QOS_0)
        ])


    # let's abruptly disconnect client1
    await client1.cancel_tasks()
    if client1._disconnect_task and not client1._disconnect_task.done():
        client1._disconnect_task.cancel()
    client1._connected_state.clear()
    await client1._handler.stop()
    client1.session.transitions.disconnect()

    await asyncio.sleep(0.5)

    # make sure the client which is still connected that we get the 'will' message
    message = await client2.deliver_message(timeout_duration=1)
    assert message.topic == 'test/will/topic'
    assert message.data == b'client ABC has disconnected'
    await client2.disconnect()

    # make sure a client which is connected after client1 disconnected still receives the 'will' message from
    client3 = MQTTClient(client_id="client3")
    await client3.connect('mqtt://localhost:1883')
    await client3.subscribe([
        ("test/will/topic", QOS_0)
    ])
    message3 = await client3.deliver_message(timeout_duration=1)
    assert message3.topic == 'test/will/topic'
    assert message3.data == b'client ABC has disconnected'
    await client3.disconnect()


@pytest.mark.asyncio
async def test_client_abruptly_disconnecting_with_empty_will_message(broker_fixture):

    config = {
        "will": {
            "topic": "test/will/topic",
            "retain": True,
            "message": "",
            "qos": 1
        },
    }
    client1 = MQTTClient(client_id="client1", config=config)
    await client1.connect('mqtt://localhost:1883')

    client2 = MQTTClient(client_id="client2")
    await client2.connect('mqtt://localhost:1883')
    await client2.subscribe([
        ("test/will/topic", QOS_0)
    ])

    # let's abruptly disconnect client1
    await client1.cancel_tasks()
    if client1._disconnect_task and not client1._disconnect_task.done():
        client1._disconnect_task.cancel()
    client1._connected_state.clear()
    await client1._handler.stop()
    client1.session.transitions.disconnect()

    await asyncio.sleep(0.5)

    message = await client2.deliver_message(timeout_duration=1)
    assert message.topic == 'test/will/topic'
    assert message.data == b''

    await client2.disconnect()


async def test_connect_broken_uri():
    config = {"auto_reconnect": False}
    client = MQTTClient(config=config)
    with pytest.raises(ClientError):
        await client.connect('"mqtt://someplace')


@pytest.mark.asyncio
async def test_connect_incorrect_scheme():
    config = {"auto_reconnect": False}
    client = MQTTClient(config=config)
    with pytest.raises(ClientError):
        await client.connect('"mq://someplace')


async def test_client_no_auth():


    class MockEntryPoints:

        def select(self, group) -> list[EntryPoint]:
            match group:
                case 'tests.mock_plugins':
                    return [
                            EntryPoint(name='auth_plugin', group='tests.mock_plugins', value='tests.plugins.mocks:NoAuthPlugin'),
                        ]
                case _:
                    return list()


    with patch("amqtt.plugins.manager.entry_points", side_effect=MockEntryPoints) as mocked_mqtt_publish:

        config = {
            "listeners": {
                "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
            },
            'sys_interval': 1,
            'auth': {
                'plugins': ['auth_plugin', ]
            }
        }

        client = MQTTClient(client_id="client1", config={'auto_reconnect': False})

        broker = Broker(plugin_namespace='tests.mock_plugins', config=config)
        await broker.start()

        with pytest.raises(ConnectError):
            await client.connect("mqtt://127.0.0.1:1883/")

        await broker.shutdown()
