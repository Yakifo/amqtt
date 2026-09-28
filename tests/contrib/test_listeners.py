import asyncio
from contextlib import suppress
from pathlib import Path
import ssl
from typing import Callable

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.contexts import BrokerConfig, ListenerConfig, ListenerType
from amqtt.contrib import listeners as listeners_module
from amqtt.contrib.listeners import ReloadableExternalTLSListener


def external_broker_config() -> BrokerConfig:
    return BrokerConfig(
        listeners={
            "default": ListenerConfig(type=ListenerType.EXTERNAL),
        },
        plugins={
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                "allow_anonymous": True,
            },
        },
    )


async def wait_until(predicate: Callable[[], bool], timeout: float = 2) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            msg = "condition was not satisfied before timeout"
            raise AssertionError(msg)
        await asyncio.sleep(0.01)


@pytest.fixture
async def external_broker():
    broker = Broker(external_broker_config())
    await broker.start()
    yield broker
    if not broker.transitions.is_stopped():
        await broker.shutdown()


def make_server_ssl_context(certfile: Path, keyfile: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(certfile), str(keyfile))
    return context


def make_file_context_factory(certfile: Path, keyfile: Path) -> Callable[[], ssl.SSLContext]:
    return lambda: make_server_ssl_context(certfile, keyfile)


def make_unstarted_listener(
    broker: Broker,
    certfile: Path,
    keyfile: Path,
    **kwargs,
) -> ReloadableExternalTLSListener:
    return ReloadableExternalTLSListener(
        broker=broker,
        listener_name=kwargs.pop("listener_name", "default"),
        host=kwargs.pop("host", "127.0.0.1"),
        port=kwargs.pop("port", 0),
        ssl_context_factory=kwargs.pop("ssl_context_factory", make_file_context_factory(certfile, keyfile)),
        **kwargs,
    )


def make_tls_client(client_id: str) -> MQTTClient:
    return MQTTClient(
        client_id=client_id,
        config={
            "auto_reconnect": False,
            "check_hostname": False,
            "verify_cert": False,
        },
    )


async def disconnect_client(client: MQTTClient) -> None:
    if client.session and client.session.transitions.is_connected():
        with suppress(Exception):
            await client.disconnect()


@pytest.mark.asyncio
async def test_reloadable_tls_listener_accepts_mqtts_and_tracks_connections(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    listener = ReloadableExternalTLSListener(
        broker=external_broker,
        listener_name="default",
        host="127.0.0.1",
        port=0,
        ssl_context_factory=make_file_context_factory(certfile, keyfile),
    )
    client = make_tls_client("client-1")

    await listener.start()
    try:
        assert listener.actual_port is not None
        await client.connect(f"mqtts://127.0.0.1:{listener.actual_port}")

        await wait_until(lambda: listener.active_connection_count == 1)
        await client.publish("reloadable/topic", b"payload")

        await client.disconnect()
        await wait_until(lambda: listener.active_connection_count == 0)
    finally:
        await disconnect_client(client)
        await listener.close()


@pytest.mark.asyncio
async def test_reload_replaces_accept_socket_without_dropping_existing_connections(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
    unused_tcp_port: int,
) -> None:
    certfile, keyfile = rsa_keys
    first_context = make_server_ssl_context(certfile, keyfile)
    second_context = make_server_ssl_context(certfile, keyfile)
    listener = ReloadableExternalTLSListener(
        broker=external_broker,
        listener_name="default",
        host="127.0.0.1",
        port=unused_tcp_port,
        ssl_context_factory=lambda: first_context,
    )
    first_client = make_tls_client("first-client")
    second_client = make_tls_client("second-client")

    await listener.start()
    try:
        assert listener.actual_port is not None
        first_port = listener.actual_port
        assert first_port == unused_tcp_port
        await first_client.connect(f"mqtts://127.0.0.1:{first_port}")
        await wait_until(lambda: listener.active_connection_count == 1)

        await listener.reload(lambda: second_context)

        assert listener.ssl_context is second_context
        assert listener.active_connection_count == 1
        assert listener.actual_port == first_port

        await first_client.publish("reloadable/topic", b"still connected")
        await second_client.connect(f"mqtts://127.0.0.1:{listener.actual_port}")
        await wait_until(lambda: listener.active_connection_count == 2)
    finally:
        await disconnect_client(second_client)
        await disconnect_client(first_client)
        await listener.close()


@pytest.mark.asyncio
async def test_failed_reload_preserves_existing_listener(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    listener = ReloadableExternalTLSListener(
        broker=external_broker,
        listener_name="default",
        host="127.0.0.1",
        port=0,
        ssl_context_factory=make_file_context_factory(certfile, keyfile),
    )
    client = make_tls_client("client-after-failed-reload")

    await listener.start()
    try:
        old_context = listener.ssl_context
        old_port = listener.actual_port

        def fail_factory() -> ssl.SSLContext:
            msg = "invalid replacement TLS material"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="invalid replacement"):
            await listener.reload(fail_factory)

        assert listener.ssl_context is old_context
        assert listener.actual_port == old_port
        assert old_port is not None

        await client.connect(f"mqtts://127.0.0.1:{old_port}")
        await wait_until(lambda: listener.active_connection_count == 1)
    finally:
        await disconnect_client(client)
        await listener.close()


@pytest.mark.asyncio
async def test_listener_requires_started_external_broker_listener(
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    tcp_broker = Broker(
        BrokerConfig(
            listeners={"default": ListenerConfig(type=ListenerType.TCP, bind="127.0.0.1:0")},
            plugins={},
        ),
    )
    listener = ReloadableExternalTLSListener(
        broker=tcp_broker,
        listener_name="default",
        host="127.0.0.1",
        port=0,
        ssl_context_factory=make_file_context_factory(certfile, keyfile),
    )

    with pytest.raises(ValueError, match="ListenerType.EXTERNAL"):
        await listener.start()


@pytest.mark.asyncio
async def test_listener_constructor_and_idle_state_validation(
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    broker = Broker(external_broker_config())

    with pytest.raises(ValueError, match="port"):
        make_unstarted_listener(broker, certfile, keyfile, port=-1)
    with pytest.raises(ValueError, match="backlog"):
        make_unstarted_listener(broker, certfile, keyfile, backlog=0)

    listener = make_unstarted_listener(broker, certfile, keyfile)
    assert listener.sockets == ()
    assert listener.actual_port is None
    assert not listener.is_serving


@pytest.mark.asyncio
async def test_listener_start_validation_errors(
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    unstarted_broker = Broker(external_broker_config())
    listener = make_unstarted_listener(unstarted_broker, certfile, keyfile)

    with pytest.raises(RuntimeError, match="Broker must be started"):
        await listener.start()

    started_broker = Broker(
        BrokerConfig(
            listeners={"default": ListenerConfig(type=ListenerType.EXTERNAL)},
            plugins={},
        ),
    )
    await started_broker.start()
    try:
        missing_listener = make_unstarted_listener(started_broker, certfile, keyfile, listener_name="missing")
        with pytest.raises(ValueError, match="not configured"):
            await missing_listener.start()

        stale_listener = make_unstarted_listener(started_broker, certfile, keyfile)
        started_broker._servers.clear()
        with pytest.raises(RuntimeError, match="not active"):
            await stale_listener.start()
    finally:
        if not started_broker.transitions.is_stopped():
            await started_broker.shutdown()


@pytest.mark.asyncio
async def test_listener_lifecycle_error_paths(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    listener = make_unstarted_listener(external_broker, certfile, keyfile, ssl_handshake_timeout=2)

    await listener.close()
    await listener.wait_connections_closed()
    with pytest.raises(RuntimeError, match="not started"):
        await listener.reload()

    await listener.start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            await listener.start()
    finally:
        await listener.close()


@pytest.mark.asyncio
async def test_listener_async_context_manager_closes_accept_socket(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    listener = make_unstarted_listener(external_broker, certfile, keyfile)

    async with listener as running_listener:
        assert running_listener is listener
        assert listener.is_serving

    assert not listener.is_serving
    assert listener.ssl_context is None


@pytest.mark.asyncio
async def test_build_ssl_context_rejects_invalid_factory_result(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    listener = make_unstarted_listener(
        external_broker,
        certfile,
        keyfile,
        ssl_context_factory=lambda: object(),
    )

    with pytest.raises(TypeError, match="ssl.SSLContext"):
        await listener.start()


@pytest.mark.asyncio
async def test_reload_rolls_back_when_replacement_socket_cannot_start(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certfile, keyfile = rsa_keys
    first_context = make_server_ssl_context(certfile, keyfile)
    second_context = make_server_ssl_context(certfile, keyfile)
    listener = make_unstarted_listener(external_broker, certfile, keyfile, ssl_context_factory=lambda: first_context)
    original_create_server = listener._create_server

    async def create_server_or_fail(context: ssl.SSLContext) -> asyncio.Server:
        if context is second_context:
            msg = "replacement socket failed"
            raise OSError(msg)
        return await original_create_server(context)

    await listener.start()
    monkeypatch.setattr(listener, "_create_server", create_server_or_fail)
    try:
        with pytest.raises(OSError, match="replacement socket failed"):
            await listener.reload(lambda: second_context)

        assert listener.ssl_context is first_context
        assert listener.is_serving
    finally:
        await listener.close()


@pytest.mark.asyncio
async def test_connection_failure_closes_writer_and_clears_tracking(
    external_broker: Broker,
    rsa_keys: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certfile, keyfile = rsa_keys
    listener = make_unstarted_listener(external_broker, certfile, keyfile)
    adapters = []

    class RecordingWriterAdapter:
        def __init__(self, writer) -> None:
            self.writer = writer
            self.close_count = 0
            adapters.append(self)

        async def close(self) -> None:
            self.close_count += 1

    async def fail_external_connected(*_args, **_kwargs) -> None:
        assert listener.active_connection_count == 1
        msg = "handoff failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(listeners_module, "StreamWriterAdapter", RecordingWriterAdapter)
    monkeypatch.setattr(external_broker, "external_connected", fail_external_connected)

    writer = object()
    await listener._client_connected(asyncio.StreamReader(), writer)

    assert listener.active_connection_count == 0
    assert len(adapters) == 1
    assert adapters[0].writer is writer
    assert adapters[0].close_count == 1
