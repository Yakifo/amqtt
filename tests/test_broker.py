import asyncio
import logging
import socket
from unittest.mock import MagicMock, call, patch

import psutil
import pytest

from amqtt.events import BrokerEvents
from amqtt.adapters import StreamReaderAdapter, StreamWriterAdapter
from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.errors import ConnectError
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket, ConnectPayload, ConnectVariableHeader
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.mqtt.disconnect import DisconnectPacket
from amqtt.mqtt.protocol.broker_handler import BrokerProtocolHandler
from amqtt.mqtt.pubcomp import PubcompPacket
from amqtt.mqtt.publish import PublishPacket
from amqtt.mqtt.pubrec import PubrecPacket
from amqtt.mqtt.pubrel import PubrelPacket
from amqtt.session import OutgoingApplicationMessage

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)
log = logging.getLogger(__name__)


# monkey patch MagicMock
# taken from https://stackoverflow.com/questions/51394411/python-object-magicmock-cant-be-used-in-await-expression
async def async_magic():
    pass


MagicMock.__await__ = lambda _: async_magic().__await__()


@pytest.mark.parametrize(
    "input_str, output_addr, output_port",
    [
        ("1234", None, 1234),
        (":1234", None, 1234),
        ("0.0.0.0:1234", "0.0.0.0", 1234),
        ("[::]:1234", "[::]", 1234),
        ("0.0.0.0", "0.0.0.0", 5678),
        ("[::]", "[::]", 5678),
        ("localhost", "localhost", 5678),
        ("localhost:1234", "localhost", 1234),
    ],
)
def test_split_bindaddr_port(input_str, output_addr, output_port):
    assert Broker._split_bindaddr_port(input_str, 5678) == (output_addr, output_port)


@pytest.mark.asyncio
async def test_start_stop(broker, mock_plugin_manager):
    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(BrokerEvents.PRE_START),
            call().fire_event(BrokerEvents.POST_START),
        ],
        any_order=True,
    )
    mock_plugin_manager.reset_mock()
    await broker.shutdown()
    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(BrokerEvents.PRE_SHUTDOWN),
            call().fire_event(BrokerEvents.POST_SHUTDOWN),
        ],
        any_order=True,
    )
    assert broker.transitions.is_stopped()


@pytest.mark.asyncio
async def test_client_connect(broker, mock_plugin_manager):
    client = MQTTClient()
    ret = await client.connect("mqtt://127.0.0.1/")
    assert ret == 0
    assert client.session is not None
    assert client.session.client_id in broker._sessions
    await client.disconnect()

    await asyncio.sleep(0.01)

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                BrokerEvents.CLIENT_CONNECTED,
                client_id=client.session.client_id,
            ),
            call().fire_event(
                BrokerEvents.CLIENT_DISCONNECTED,
                client_id=client.session.client_id,
            ),
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_connect_tcp(broker):
    process = psutil.Process()
    connections_number = 10

    # mqtt 3.1 requires a connect packet, otherwise the socket connection is rejected
    static_connect_packet = b'\x10\x1b\x00\x04MQTT\x04\x02\x00<\x00\x0ftest-client-123'

    sockets = []
    for i in range(connections_number):
        s = socket.create_connection(("127.0.0.1", 1883))
        s.send(static_connect_packet)
        sockets.append(s)

    # Wait for a brief moment to ensure connections are established
    await asyncio.sleep(0.1)

    # # Get the current number of TCP connections
    connections = process.net_connections()

    # max number of connections on the TCP listener is 10
    assert broker._servers["default"].conn_count == connections_number

    # Ensure connections are only on the TCP listener (port 1883)
    tcp_connections = [conn for conn in connections if conn.laddr.port == 1883]
    assert len(tcp_connections) == connections_number + 1  # Including the Broker's listening socket

    for conn in connections:
        assert conn.status in ("ESTABLISHED", "LISTEN")

    # close all connections
    for s in sockets:
        s.close()

    # Wait a moment for connections to be closed
    await asyncio.sleep(0.1)

    # Recheck connections after closing
    connections = process.net_connections()
    tcp_connections = [conn for conn in connections if conn.laddr.port == 1883]

    for conn in tcp_connections:
        assert conn.status in ("CLOSE_WAIT", "LISTEN")

    # Ensure no active connections for the default listener
    assert broker._servers["default"].conn_count == 0

    # Add one more connection to the TCP listener
    s = socket.create_connection(("127.0.0.1", 1883))
    s.send(static_connect_packet)

    open_connections = []
    open_connections = [conn for conn in process.net_connections() if conn.status == "ESTABLISHED"]

    # Ensure that only one TCP connection is active now
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
    connect = ConnectPacket(variable_header=vh, payload=payload)
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
    except ConnectError as ce:
        return_code = ce.return_code
    assert return_code == 0x02
    assert client.session is not None
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
                BrokerEvents.CLIENT_SUBSCRIBED,
                client_id=client.session.client_id,
                topic="/topic",
                qos=QOS_0,
            ),
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
                BrokerEvents.CLIENT_SUBSCRIBED,
                client_id=client.session.client_id,
                topic="/topic",
                qos=QOS_0,
            ),
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
                BrokerEvents.CLIENT_SUBSCRIBED,
                client_id=client.session.client_id,
                topic="/topic",
                qos=QOS_0,
            ),
            call().fire_event(
                BrokerEvents.CLIENT_UNSUBSCRIBED,
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
    assert pub_client.session is not None

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                BrokerEvents.MESSAGE_RECEIVED,
                client_id=pub_client.session.client_id,
                message=ret_message,
            ),
        ],
        any_order=True,
    )


@pytest.mark.asyncio
async def test_client_publish_acl_permitted(acl_broker):
    sub_client = MQTTClient()
    ret_conn = await sub_client.connect("mqtt://user2:user2password@127.0.0.1:1884/")
    assert ret_conn == 0

    ret_sub = await sub_client.subscribe([("public/subtopic/test", QOS_0)])
    assert ret_sub == [QOS_0]

    pub_client = MQTTClient()
    ret_conn = await pub_client.connect("mqtt://user1:user1password@127.0.0.1:1884/")
    assert ret_conn == 0

    await pub_client.publish("public/subtopic/test", b"data", QOS_0)

    message = await sub_client.deliver_message(timeout_duration=1)
    await pub_client.disconnect()
    await sub_client.disconnect()

    assert message is not None
    assert message.topic == "public/subtopic/test"
    assert message.data == b"data"
    assert message.qos == QOS_0


@pytest.mark.asyncio
async def test_client_publish_acl_forbidden(acl_broker):
    sub_client = MQTTClient()
    ret_conn = await sub_client.connect("mqtt://user2:user2password@127.0.0.1:1884/")
    assert ret_conn == 0

    ret_sub = await sub_client.subscribe([("public/forbidden/test", QOS_0)])
    assert ret_sub == [QOS_0]

    pub_client = MQTTClient()
    ret_conn = await pub_client.connect("mqtt://user1:user1password@127.0.0.1:1884/")
    assert ret_conn == 0

    await pub_client.publish("public/forbidden/test", b"data", QOS_0)

    try:
        await sub_client.deliver_message(timeout_duration=1)
        msg = "Should not have worked"
        raise AssertionError(msg)
    except Exception:
        pass

    await pub_client.disconnect()
    await sub_client.disconnect()


@pytest.mark.asyncio
async def test_client_publish_acl_permitted_sub_forbidden(acl_broker):
    sub_client1 = MQTTClient()
    ret_conn = await sub_client1.connect("mqtt://user2:user2password@127.0.0.1:1884/")
    assert ret_conn == 0

    sub_client2 = MQTTClient()
    ret_conn = await sub_client2.connect("mqtt://user3:user3password@127.0.0.1:1884/")
    assert ret_conn == 0

    ret_sub = await sub_client1.subscribe([("public/subtopic/test", QOS_0)])
    assert ret_sub == [QOS_0]

    ret_sub = await sub_client2.subscribe([("public/subtopic/test", QOS_0)])
    assert ret_sub == [128]

    pub_client = MQTTClient()
    ret_conn = await pub_client.connect("mqtt://user1:user1password@127.0.0.1:1884/")
    assert ret_conn == 0

    await pub_client.publish("public/subtopic/test", b"data", QOS_0)

    message = await sub_client1.deliver_message(timeout_duration=1)

    try:
        await sub_client2.deliver_message(timeout_duration=1)
        msg = "Should not have worked"
        raise AssertionError(msg)
    except Exception:
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
    connect = ConnectPacket(variable_header=vh, payload=payload)
    await connect.to_stream(writer)
    await ConnackPacket.from_stream(reader)

    publish_1 = PublishPacket.build("/test", b"data", 1, False, QOS_2, False)
    await publish_1.to_stream(writer)

    # Store the future of PubrecPacket.from_stream() in a variable
    pubrec_task_1 = asyncio.ensure_future(PubrecPacket.from_stream(reader))

    await asyncio.sleep(2)

    publish_dup = PublishPacket.build("/test", b"data", 1, True, QOS_2, False)
    await publish_dup.to_stream(writer)
    await PubrecPacket.from_stream(reader)
    pubrel = PubrelPacket.build(1)
    await pubrel.to_stream(writer)
    await PubcompPacket.from_stream(reader)

    # Ensure we wait for the Pubrec packets to be processed
    await pubrec_task_1

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
        "/topic",
        bytearray(b"\x99" * 256 * 1024),
        QOS_2,
    )
    await pub_client.disconnect()
    assert broker._retained_messages == {}

    await asyncio.sleep(0.1)
    assert pub_client.session is not None

    mock_plugin_manager.assert_has_calls(
        [
            call().fire_event(
                BrokerEvents.MESSAGE_RECEIVED,
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
        [("/qos0", QOS_0), ("/qos1", QOS_1), ("/qos2", QOS_2)],
    )
    assert ret == [QOS_0, QOS_1, QOS_2]

    await _client_publish("/qos0", b"data", QOS_0)
    await _client_publish("/qos1", b"data", QOS_1)
    await _client_publish("/qos2", b"data", QOS_2)
    await asyncio.sleep(0.1)
    for qos in [QOS_0, QOS_1, QOS_2]:
        message = await sub_client.deliver_message()
        assert message is not None
        assert message.topic == f"/qos{qos}"
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
        ],
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
        message = await sub_client.deliver_message(timeout_duration=2)
    except Exception:
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
        message = await sub_client.deliver_message(timeout_duration=2)
    except Exception:
        pass
    except RuntimeError as e:
        # The loop is closed with pending tasks. Needs fine tuning.
        log.warning(e)
    assert message is None
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_client_publish_retain_subscribe(broker):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1", cleansession=False)
    ret = await sub_client.subscribe(
        [("/qos0", QOS_0), ("/qos1", QOS_1), ("/qos2", QOS_2)],
    )
    assert ret == [QOS_0, QOS_1, QOS_2]
    await sub_client.disconnect()
    await asyncio.sleep(0.1)

    await _client_publish("/qos0", b"data", QOS_0, retain=True)
    await _client_publish("/qos1", b"data", QOS_1, retain=True)
    await _client_publish("/qos2", b"data", QOS_2, retain=True)
    await sub_client.reconnect()
    for qos in [QOS_0, QOS_1, QOS_2]:
        log.debug(f"TEST QOS: {qos}")
        message = await sub_client.deliver_message()
        log.debug(f"Message: {message.publish_packet if message else None!r}")
        assert message is not None
        assert message.topic == f"/qos{qos}"
        assert message.data == b"data"
        assert message.qos == qos
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def _client_publish(topic, data, qos, retain=False) -> int | OutgoingApplicationMessage:
    pub_client = MQTTClient()
    ret: int | OutgoingApplicationMessage = await pub_client.connect("mqtt://127.0.0.1/")
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
        assert not broker._matches(bad_topic, test_filter)

    for good_topic in [
        "sport/tennis/player1",
        "sport/tennis/player1/",
        "sport/tennis/player1/ranking",
        "sport/tennis/player1/score/wimbledon",
    ]:
        assert broker._matches(good_topic, test_filter)


def test_matches_single_level_wildcard(broker):
    test_filter = "sport/tennis/+"

    for bad_topic in [
        "sport/tennis",
        "sport/tennis/player1/",
        "sport/tennis/player1/ranking",
    ]:
        assert not broker._matches(bad_topic, test_filter)

    for good_topic in [
        "sport/tennis/",
        "sport/tennis/player1",
        "sport/tennis/player2",
    ]:
        assert broker._matches(good_topic, test_filter)


@pytest.mark.asyncio
async def test_broker_broadcast_cancellation(broker):
    topic = "test"
    data = b"data"
    qos = QOS_0

    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe([(topic, qos)])

    with patch.object(BrokerProtocolHandler, "mqtt_publish", side_effect=asyncio.CancelledError) as mocked_mqtt_publish:
        await _client_publish(topic, data, qos)

        # Second publish triggers the awaiting of first `mqtt_publish` task
        await _client_publish(topic, data, qos)
        await asyncio.sleep(0.01)

        mocked_mqtt_publish.assert_awaited()

    # Ensure broadcast loop is still functional and can deliver the message
    await _client_publish(topic, data, qos)
    message = await asyncio.wait_for(sub_client.deliver_message(), timeout=1)
    assert message


@pytest.mark.asyncio
async def test_broker_socket_open_close(broker):

    # check that https://github.com/Yakifo/amqtt/issues/86 is fixed

    # mqtt 3.1 requires a connect packet, otherwise the socket connection is rejected
    static_connect_packet = b'\x10\x1b\x00\x04MQTT\x04\x02\x00<\x00\x0ftest-client-123'
    s = socket.create_connection(("127.0.0.1", 1883))
    s.send(static_connect_packet)
    await asyncio.sleep(0.1)
    s.close()
