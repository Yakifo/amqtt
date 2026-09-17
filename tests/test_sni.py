import asyncio
import logging
import ssl
from collections.abc import Callable
from pathlib import Path

import pytest

from amqtt.adapters import BufferReader, BufferWriter
from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.errors import AMQTTError, NoDataError
from amqtt.mqtt.protocol.broker_handler import BrokerProtocolHandler
from amqtt.session import Session


class SNIWriter(BufferWriter):
    def __init__(self, ssl_object: ssl.SSLObject | None) -> None:
        super().__init__()
        self._ssl_object = ssl_object
        self.closed = False

    def get_ssl_info(self) -> ssl.SSLObject | None:
        return self._ssl_object

    async def close(self) -> None:
        self.closed = True


def make_ssl_object() -> ssl.SSLObject:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context.wrap_bio(ssl.MemoryBIO(), ssl.MemoryBIO())


async def wait_for_log(caplog: pytest.LogCaptureFixture, predicate: Callable[[str], bool]) -> None:
    for _ in range(20):
        if predicate(caplog.text):
            return
        await asyncio.sleep(0.05)


def make_broker(mock_plugin_manager: object) -> Broker:
    assert mock_plugin_manager is not None
    return Broker()


@pytest.mark.asyncio
async def test_tls_session_records_inbound_sni(rsa_keys: tuple[Path, Path], broker_fixture: Broker) -> None:
    certfile, _ = rsa_keys
    client = MQTTClient(config={"check_hostname": False, "auto_reconnect": False})

    await client.connect("mqtts://localhost:1884/", cafile=certfile)

    assert client.session is not None
    broker_session, _ = broker_fixture._sessions[client.session.client_id]
    assert broker_session.ssl_object is not None
    assert broker_session.inbound_sni == "localhost"
    assert len(broker_fixture._inbound_sni_by_ssl_object) == 0

    await client.disconnect()


@pytest.mark.asyncio
async def test_tls_disconnect_before_mqtt_connect_logs_inbound_sni(
    rsa_keys: tuple[Path, Path],
    broker_fixture: Broker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    certfile, _ = rsa_keys
    caplog.set_level(logging.WARNING, logger="amqtt.broker")

    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=certfile)
    context.check_hostname = False
    _, writer = await asyncio.open_connection(
        "127.0.0.1",
        1884,
        ssl=context,
        server_hostname="diagnostic.example",
    )

    writer.close()
    await writer.wait_closed()

    await wait_for_log(caplog, lambda text: "closed before MQTT CONNECT" in text)

    assert "TLS connection from" in caplog.text
    assert "127.0.0.1:" in caplog.text
    assert "on listener 'mqtts' closed before MQTT CONNECT" in caplog.text
    assert "inbound_sni='diagnostic.example'" in caplog.text
    assert len(broker_fixture._inbound_sni_by_ssl_object) == 0


@pytest.mark.asyncio
async def test_initialize_client_session_without_tls_leaves_inbound_sni_unset(
    monkeypatch: pytest.MonkeyPatch,
    mock_plugin_manager: object,
) -> None:
    broker = make_broker(mock_plugin_manager)
    incoming_session = Session()
    incoming_session.client_id = "plain-client"
    incoming_session.clean_session = True
    incoming_session.keep_alive = 0

    async def fake_init_from_connect(*_: object) -> tuple[BrokerProtocolHandler, Session]:
        return BrokerProtocolHandler(broker.plugins_manager), incoming_session

    monkeypatch.setattr(BrokerProtocolHandler, "init_from_connect", staticmethod(fake_init_from_connect))

    _, session = await broker._initialize_client_session(
        BufferReader(b""),
        SNIWriter(None),
        "127.0.0.1",
        1883,
        "default",
    )

    assert session.ssl_object is None
    assert session.inbound_sni is None


@pytest.mark.asyncio
async def test_initialize_tls_session_without_sni_leaves_inbound_sni_unset(
    monkeypatch: pytest.MonkeyPatch,
    mock_plugin_manager: object,
) -> None:
    broker = make_broker(mock_plugin_manager)
    ssl_object = make_ssl_object()
    incoming_session = Session()
    incoming_session.client_id = "tls-client"
    incoming_session.clean_session = True
    incoming_session.keep_alive = 0

    async def fake_init_from_connect(*_: object) -> tuple[BrokerProtocolHandler, Session]:
        return BrokerProtocolHandler(broker.plugins_manager), incoming_session

    broker._sni_callback(ssl_object, None, ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER))
    monkeypatch.setattr(BrokerProtocolHandler, "init_from_connect", staticmethod(fake_init_from_connect))

    _, session = await broker._initialize_client_session(
        BufferReader(b""),
        SNIWriter(ssl_object),
        "127.0.0.1",
        1884,
        "mqtts",
    )

    assert session.ssl_object is ssl_object
    assert session.inbound_sni is None
    assert len(broker._inbound_sni_by_ssl_object) == 0


@pytest.mark.asyncio
async def test_persistent_session_reconnect_refreshes_tls_metadata(
    monkeypatch: pytest.MonkeyPatch,
    mock_plugin_manager: object,
) -> None:
    broker = make_broker(mock_plugin_manager)
    old_ssl_object = make_ssl_object()
    new_ssl_object = make_ssl_object()

    existing_session = Session()
    existing_session.client_id = "persisted-client"
    existing_session.clean_session = False
    existing_session.remote_address = "192.0.2.1"
    existing_session.remote_port = 8883
    existing_session.ssl_object = old_ssl_object
    existing_session.inbound_sni = "old.example"
    broker._sessions["persisted-client"] = (
        existing_session,
        BrokerProtocolHandler(broker.plugins_manager, existing_session),
    )

    incoming_session = Session()
    incoming_session.client_id = "persisted-client"
    incoming_session.clean_session = False
    incoming_session.keep_alive = 15
    incoming_session.remote_address = "198.51.100.10"
    incoming_session.remote_port = 1884

    async def fake_init_from_connect(*_: object) -> tuple[BrokerProtocolHandler, Session]:
        return BrokerProtocolHandler(broker.plugins_manager), incoming_session

    broker._sni_callback(new_ssl_object, "new.example", ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER))
    monkeypatch.setattr(BrokerProtocolHandler, "init_from_connect", staticmethod(fake_init_from_connect))

    _, session = await broker._initialize_client_session(
        BufferReader(b""),
        SNIWriter(new_ssl_object),
        "198.51.100.10",
        1884,
        "mqtts",
    )

    assert session is existing_session
    assert session.remote_address == "198.51.100.10"
    assert session.remote_port == 1884
    assert session.ssl_object is new_ssl_object
    assert session.inbound_sni == "new.example"
    assert old_ssl_object is not session.ssl_object
    assert len(broker._inbound_sni_by_ssl_object) == 0


@pytest.mark.asyncio
async def test_tls_early_disconnect_consumes_captured_sni(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    mock_plugin_manager: object,
) -> None:
    broker = make_broker(mock_plugin_manager)
    ssl_object = make_ssl_object()
    writer = SNIWriter(ssl_object)

    async def fake_init_from_connect(*_: object) -> tuple[BrokerProtocolHandler, Session]:
        raise NoDataError("No more data")

    broker._sni_callback(ssl_object, "early.example", ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER))
    monkeypatch.setattr(BrokerProtocolHandler, "init_from_connect", staticmethod(fake_init_from_connect))
    caplog.set_level(logging.WARNING, logger="amqtt.broker")

    with pytest.raises(AMQTTError):
        await broker._initialize_client_session(BufferReader(b""), writer, "203.0.113.5", 55555, "mqtts")

    assert "TLS connection from" in caplog.text
    assert "203.0.113.5:55555" in caplog.text
    assert "on listener 'mqtts' closed before MQTT CONNECT" in caplog.text
    assert "inbound_sni='early.example'" in caplog.text
    assert len(broker._inbound_sni_by_ssl_object) == 0
