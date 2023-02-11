# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import asyncio
import logging
import socket
import sys
from unittest.mock import call, MagicMock, patch

import psutil
import pytest

from amqtt.adapters import StreamReaderAdapter, StreamWriterAdapter
from amqtt.broker import (
    EVENT_BROKER_PRE_START,
    EVENT_BROKER_POST_START,
    EVENT_BROKER_PRE_SHUTDOWN,
    EVENT_BROKER_POST_SHUTDOWN,
    EVENT_BROKER_CLIENT_CONNECTED,
    EVENT_BROKER_CLIENT_DISCONNECTED,
    EVENT_BROKER_CLIENT_SUBSCRIBED,
    EVENT_BROKER_CLIENT_UNSUBSCRIBED,
    EVENT_BROKER_MESSAGE_RECEIVED,
)
from amqtt.client import MQTTClient, ConnectException
from amqtt.mqtt import (
    ConnectPacket,
    ConnackPacket,
    PublishPacket,
    PubrecPacket,
    PubrelPacket,
    PubcompPacket,
    DisconnectPacket,
)
from amqtt.mqtt.connect import ConnectVariableHeader, ConnectPayload
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.mqtt.protocol.broker_handler import BrokerProtocolHandler


formatter = (
    "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
)
logging.basicConfig(level=logging.DEBUG, format=formatter)
log = logging.getLogger(__name__)


# monkey patch MagicMock
# taken from https://stackoverflow.com/questions/51394411/python-object-magicmock-cant-be-used-in-await-expression
async def async_magic():
    pass


MagicMock.__await__ = lambda x: async_magic().__await__()


@pytest.mark.asyncio
async def test_start_stop(broker, mock_plugin_manager):
    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(EVENT_BROKER_PRE_START),
            call().fire_event(EVENT_BROKER_POST_START),
        ],
        any_order=True,
    )
    mock_plugin_manager.reset_mock()
    await broker.shutdown()
    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(EVENT_BROKER_PRE_SHUTDOWN),
            call().fire_event(EVENT_BROKER_POST_SHUTDOWN),
        ],
        any_order=True,
    )
    assert broker.transitions.is_stopped()


@pytest.mark.asyncio
async def test_client_connect(broker, mock_plugin_manager):
    client = MQTTClient()
    ret = await client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    assert client.session.client_id in broker._sessions
    await client.disconnect()

    await asyncio.sleep(0.01)

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                EVENT_BROKER_CLIENT_CONNECTED, client_id=client.session.client_id
            ),
            call().fire_event(
                EVENT_BROKER_CLIENT_DISCONNECTED, client_id=client.session.client_id
            ),
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_connect_tcp(broker):
    process = psutil.Process()
    connections_number = 10
    sockets = [
        socket.create_connection(("127.0.0.1", 1883)) for _ in range(connections_number)
    ]
    connections = process.connections()
    await asyncio.sleep(0.1)

    # max number of connections is 10
    assert broker._servers["default"].conn_count == connections_number
    # Extra connection for the listening Broker
    assert len(connections) == connections_number + 1
    for conn in connections:
        assert conn.status == "ESTABLISHED" or conn.status == "LISTEN"

    # close all connections
    for s in sockets:
        s.close()
    connections = process.connections()
    for conn in connections:
        assert conn.status == "CLOSE_WAIT" or conn.status == "LISTEN"
    await asyncio.sleep(0.1)
    assert broker._servers["default"].conn_count == 0

    # Add one more connection
    s = socket.create_connection(("127.0.0.1", 1883))
    open_connections = []
    for conn in process.connections():
        if conn.status == "ESTABLISHED":
            open_connections.append(conn)
    assert len(open_connections) == 1
    await asyncio.sleep(0.1)
    assert broker._servers["default"].conn_count == 1


@pytest.mark.asyncio
async def test_client_connect_will_flag(broker):
    conn_reader, conn_writer = await asyncio.open_connection("127.0.0.1", 1883)
    reader = StreamReaderAdapter(conn_reader)
    writer = StreamWriterAdapter(conn_writer)

    vh = ConnectVariableHeader()
    payload = ConnectPayload()

    vh.keep_alive = 10
    vh.clean_session_flag = False
    vh.will_retain_flag = False
    vh.will_flag = True
    vh.will_qos = QOS_0
    payload.client_id = "test_id"
    payload.will_message = b"test"
    payload.will_topic = "/topic"
    connect = ConnectPacket(vh=vh, payload=payload)
    await connect.to_stream(writer)
    await ConnackPacket.from_stream(reader)

    await asyncio.sleep(0.1)

    disconnect = DisconnectPacket()
    await disconnect.to_stream(writer)

    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_client_connect_clean_session_false(broker):
    client = MQTTClient(client_id="", config={"auto_reconnect": False})
    return_code = None
    try:
        await client.connect("mqtt://127.0.0.1/", cleansession=False)
    except ConnectException as ce:
        return_code = ce.return_code
    assert return_code == 0x02
    assert client.session.client_id not in broker._sessions
    await client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_client_subscribe(broker, mock_plugin_manager):
    client = MQTTClient()
    ret = await client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    await client.subscribe([("/topic", QOS_0)])

    # Test if the client test client subscription is registered
    assert "/topic" in broker._subscriptions
    subs = broker._subscriptions["/topic"]
    assert len(subs) == 1
    (s, qos) = subs[0]
    assert s == client.session
    assert qos == QOS_0

    await client.disconnect()
    await asyncio.sleep(0.1)

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                EVENT_BROKER_CLIENT_SUBSCRIBED,
                client_id=client.session.client_id,
                topic="/topic",
                qos=QOS_0,
            )
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_client_subscribe_twice(broker, mock_plugin_manager):
    client = MQTTClient()
    ret = await client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    await client.subscribe([("/topic", QOS_0)])

    # Test if the client test client subscription is registered
    assert "/topic" in broker._subscriptions
    subs = broker._subscriptions["/topic"]
    assert len(subs) == 1
    (s, qos) = subs[0]
    assert s == client.session
    assert qos == QOS_0

    await client.subscribe([("/topic", QOS_0)])
    assert len(subs) == 1
    (s, qos) = subs[0]
    assert s == client.session
    assert qos == QOS_0

    await client.disconnect()
    await asyncio.sleep(0.1)

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                EVENT_BROKER_CLIENT_SUBSCRIBED,
                client_id=client.session.client_id,
                topic="/topic",
                qos=QOS_0,
            )
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_client_unsubscribe(broker, mock_plugin_manager):
    client = MQTTClient()
    ret = await client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    await client.subscribe([("/topic", QOS_0)])

    # Test if the client test client subscription is registered
    assert "/topic" in broker._subscriptions
    subs = broker._subscriptions["/topic"]
    assert len(subs) == 1
    (s, qos) = subs[0]
    assert s == client.session
    assert qos == QOS_0

    await client.unsubscribe(["/topic"])
    await asyncio.sleep(0.1)
    assert broker._subscriptions["/topic"] == []
    await client.disconnect()
    await asyncio.sleep(0.1)

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                EVENT_BROKER_CLIENT_SUBSCRIBED,
                client_id=client.session.client_id,
                topic="/topic",
                qos=QOS_0,
            ),
            call().fire_event(
                EVENT_BROKER_CLIENT_UNSUBSCRIBED,
                client_id=client.session.client_id,
                topic="/topic",
            ),
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_client_publish(broker, mock_plugin_manager):
    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://127.0.0.1/")
    assert ret == 0

    ret_message = await pub_client.publish("/topic", b"data", QOS_0)
    await pub_client.disconnect()
    assert broker._retained_messages == {}

    await asyncio.sleep(0.1)

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                EVENT_BROKER_MESSAGE_RECEIVED,
                client_id=pub_client.session.client_id,
                message=ret_message,
            ),
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_client_publish_acl_permitted(acl_broker):
    sub_client = MQTTClient()
    ret = await sub_client.connect("mqtt://user2:user2password@127.0.0.1:1884/")
    assert ret == 0

    ret = await sub_client.subscribe([("public/subtopic/test", QOS_0)])
    assert ret == [QOS_0]

    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://user1:user1password@127.0.0.1:1884/")
    assert ret == 0

    await pub_client.publish("public/subtopic/test", b"data", QOS_0)

    message = await sub_client.deliver_message(timeout=1)
    await pub_client.disconnect()
    await sub_client.disconnect()

    assert message is not None
    assert message.topic == "public/subtopic/test"
    assert message.data == b"data"
    assert message.qos == QOS_0


@pytest.mark.asyncio
async def test_client_publish_acl_forbidden(acl_broker):
    sub_client = MQTTClient()
    ret = await sub_client.connect("mqtt://user2:user2password@127.0.0.1:1884/")
    assert ret == 0

    ret = await sub_client.subscribe([("public/forbidden/test", QOS_0)])
    assert ret == [QOS_0]

    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://user1:user1password@127.0.0.1:1884/")
    assert ret == 0

    await pub_client.publish("public/forbidden/test", b"data", QOS_0)

    try:
        await sub_client.deliver_message(timeout=1)
        assert False, "Should not have worked"
    except asyncio.TimeoutError:
        pass

    await pub_client.disconnect()
    await sub_client.disconnect()


@pytest.mark.asyncio
async def test_client_publish_acl_permitted_sub_forbidden(acl_broker):
    sub_client1 = MQTTClient()
    ret = await sub_client1.connect("mqtt://user2:user2password@127.0.0.1:1884/")
    assert ret == 0

    sub_client2 = MQTTClient()
    ret = await sub_client2.connect("mqtt://user3:user3password@127.0.0.1:1884/")
    assert ret == 0

    ret = await sub_client1.subscribe([("public/subtopic/test", QOS_0)])
    assert ret == [QOS_0]

    ret = await sub_client2.subscribe([("public/subtopic/test", QOS_0)])
    assert ret == [0x80]

    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://user1:user1password@127.0.0.1:1884/")
    assert ret == 0

    await pub_client.publish("public/subtopic/test", b"data", QOS_0)

    message = await sub_client1.deliver_message(timeout=1)

    try:
        await sub_client2.deliver_message(timeout=1)
        assert False, "Should not have worked"
    except asyncio.TimeoutError:
        pass

    await pub_client.disconnect()
    await sub_client1.disconnect()
    await sub_client2.disconnect()

    assert message is not None
    assert message.topic == "public/subtopic/test"
    assert message.data == b"data"
    assert message.qos == QOS_0


@pytest.mark.asyncio
async def test_client_publish_dup(broker):
    conn_reader, conn_writer = await asyncio.open_connection("127.0.0.1", 1883)
    reader = StreamReaderAdapter(conn_reader)
    writer = StreamWriterAdapter(conn_writer)

    vh = ConnectVariableHeader()
    payload = ConnectPayload()

    vh.keep_alive = 10
    vh.clean_session_flag = False
    vh.will_retain_flag = False
    payload.client_id = "test_id"
    connect = ConnectPacket(vh=vh, payload=payload)
    await connect.to_stream(writer)
    await ConnackPacket.from_stream(reader)

    publish_1 = PublishPacket.build("/test", b"data", 1, False, QOS_2, False)
    await publish_1.to_stream(writer)
    asyncio.ensure_future(PubrecPacket.from_stream(reader))

    await asyncio.sleep(2)

    publish_dup = PublishPacket.build("/test", b"data", 1, True, QOS_2, False)
    await publish_dup.to_stream(writer)
    await PubrecPacket.from_stream(reader)
    pubrel = PubrelPacket.build(1)
    await pubrel.to_stream(writer)
    await PubcompPacket.from_stream(reader)

    disconnect = DisconnectPacket()
    await disconnect.to_stream(writer)


@pytest.mark.asyncio
async def test_client_publish_invalid_topic(broker):
    assert broker.transitions.is_started()
    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://127.0.0.1/")
    assert ret == 0

    await pub_client.publish("/+", b"data", QOS_0)
    await asyncio.sleep(0.1)
    await pub_client.disconnect()


@pytest.mark.asyncio
async def test_client_publish_big(broker, mock_plugin_manager):
    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://127.0.0.1/")
    assert ret == 0

    ret_message = await pub_client.publish(
        "/topic", bytearray(b"\x99" * 256 * 1024), QOS_2
    )
    await pub_client.disconnect()
    assert broker._retained_messages == {}

    await asyncio.sleep(0.1)

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                EVENT_BROKER_MESSAGE_RECEIVED,
                client_id=pub_client.session.client_id,
                message=ret_message,
            ),
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_client_publish_retain(broker):
    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    await pub_client.publish("/topic", b"data", QOS_0, retain=True)
    await pub_client.disconnect()
    await asyncio.sleep(0.1)
    assert "/topic" in broker._retained_messages
    retained_message = broker._retained_messages["/topic"]
    assert retained_message.source_session == pub_client.session
    assert retained_message.topic == "/topic"
    assert retained_message.data == b"data"
    assert retained_message.qos == QOS_0


@pytest.mark.asyncio
async def test_client_publish_retain_delete(broker):
    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    await pub_client.publish("/topic", b"", QOS_0, retain=True)
    await pub_client.disconnect()
    await asyncio.sleep(0.1)
    assert "/topic" not in broker._retained_messages


@pytest.mark.asyncio
async def test_client_subscribe_publish(broker):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    ret = await sub_client.subscribe(
        [("/qos0", QOS_0), ("/qos1", QOS_1), ("/qos2", QOS_2)]
    )
    assert ret == [QOS_0, QOS_1, QOS_2]

    await _client_publish("/qos0", b"data", QOS_0)
    await _client_publish("/qos1", b"data", QOS_1)
    await _client_publish("/qos2", b"data", QOS_2)
    await asyncio.sleep(0.1)
    for qos in [QOS_0, QOS_1, QOS_2]:
        message = await sub_client.deliver_message()
        assert message is not None
        assert message.topic == "/qos%s" % qos
        assert message.data == b"data"
        assert message.qos == qos
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_client_subscribe_invalid(broker):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    ret = await sub_client.subscribe(
        [
            ("+", QOS_0),
            ("+/tennis/#", QOS_0),
            ("sport+", QOS_0),
            ("sport/+/player1", QOS_0),
        ]
    )
    assert ret == [QOS_0, QOS_0, 0x80, QOS_0]

    await asyncio.sleep(0.1)
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_client_subscribe_publish_dollar_topic_1(broker):
    assert broker.transitions.is_started()
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    ret = await sub_client.subscribe([("#", QOS_0)])
    assert ret == [QOS_0]

    await _client_publish("/topic", b"data", QOS_0)
    message = await sub_client.deliver_message()
    assert message is not None

    await _client_publish("$topic", b"data", QOS_0)
    await asyncio.sleep(0.1)
    message = None
    try:
        message = await sub_client.deliver_message(timeout=2)
    except asyncio.TimeoutError:
        pass
    except RuntimeError as e:
        # The loop is closed with pending tasks. Needs fine tuning.
        log.warning(e)
    assert message is None
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_client_subscribe_publish_dollar_topic_2(broker):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    ret = await sub_client.subscribe([("+/monitor/Clients", QOS_0)])
    assert ret == [QOS_0]

    await _client_publish("test/monitor/Clients", b"data", QOS_0)
    message = await sub_client.deliver_message()
    assert message is not None

    await _client_publish("$SYS/monitor/Clients", b"data", QOS_0)
    await asyncio.sleep(0.1)
    message = None
    try:
        message = await sub_client.deliver_message(timeout=2)
    except asyncio.TimeoutError:
        pass
    except RuntimeError as e:
        # The loop is closed with pending tasks. Needs fine tuning.
        log.warning(e)
    assert message is None
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="see https://github.com/Yakifo/aio-amqtt/issues/16", strict=False
)
async def test_client_publish_retain_subscribe(broker):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1", cleansession=False)
    ret = await sub_client.subscribe(
        [("/qos0", QOS_0), ("/qos1", QOS_1), ("/qos2", QOS_2)]
    )
    assert ret == [QOS_0, QOS_1, QOS_2]
    await sub_client.disconnect()
    await asyncio.sleep(0.1)

    await _client_publish("/qos0", b"data", QOS_0, retain=True)
    await _client_publish("/qos1", b"data", QOS_1, retain=True)
    await _client_publish("/qos2", b"data", QOS_2, retain=True)
    await sub_client.reconnect()
    for qos in [QOS_0, QOS_1, QOS_2]:
        log.debug("TEST QOS: %d" % qos)
        message = await sub_client.deliver_message()
        log.debug("Message: " + repr(message.publish_packet))
        assert message is not None
        assert message.topic == "/qos%s" % qos
        assert message.data == b"data"
        assert message.qos == qos
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def _client_publish(topic, data, qos, retain=False):
    pub_client = MQTTClient()
    ret = await pub_client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    ret = await pub_client.publish(topic, data, qos, retain)
    await pub_client.disconnect()
    return ret


def test_matches_multi_level_wildcard(broker):
    test_filter = "sport/tennis/player1/#"

    for bad_topic in [
        "sport/tennis",
        "sport/tennis/",
    ]:
        assert not broker.matches(bad_topic, test_filter)

    for good_topic in [
        "sport/tennis/player1",
        "sport/tennis/player1/",
        "sport/tennis/player1/ranking",
        "sport/tennis/player1/score/wimbledon",
    ]:
        assert broker.matches(good_topic, test_filter)


def test_matches_single_level_wildcard(broker):
    test_filter = "sport/tennis/+"

    for bad_topic in [
        "sport/tennis",
        "sport/tennis/player1/",
        "sport/tennis/player1/ranking",
    ]:
        assert not broker.matches(bad_topic, test_filter)

    for good_topic in [
        "sport/tennis/",
        "sport/tennis/player1",
        "sport/tennis/player2",
    ]:
        assert broker.matches(good_topic, test_filter)


@pytest.mark.asyncio
async def test_broker_broadcast_cancellation(broker):
    topic = "test"
    data = b"data"
    qos = QOS_0

    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe([(topic, qos)])

    with patch.object(
        BrokerProtocolHandler, "mqtt_publish", side_effect=asyncio.CancelledError
    ) as mocked_mqtt_publish:
        await _client_publish(topic, data, qos)

        # Second publish triggers the awaiting of first `mqtt_publish` task
        await _client_publish(topic, data, qos)
        await asyncio.sleep(0.01)

        # `assert_awaited` does not exist in Python before `3.8`
        if sys.version_info >= (3, 8):
            mocked_mqtt_publish.assert_awaited()
        else:
            mocked_mqtt_publish.assert_called()

    # Ensure broadcast loop is still functional and can deliver the message
    await _client_publish(topic, data, qos)
    message = await asyncio.wait_for(sub_client.deliver_message(), timeout=1)
    assert message
