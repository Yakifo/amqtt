"""Reloadable TLS listener support for external broker listeners."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import ssl
import tempfile
from typing import TYPE_CHECKING, Any
from typing_extensions import Self

from amqtt.adapters import StreamReaderAdapter, StreamWriterAdapter
from amqtt.contexts import ListenerType

if TYPE_CHECKING:
    import socket

    from amqtt.broker import Broker

logger = logging.getLogger(__name__)

SSLContextFactory = Callable[[], ssl.SSLContext]
NO_VERIFY_FLAGS = ssl.VerifyFlags(0)


def _path_string(path: str | Path) -> str:
    return str(path)


def _coerce_cadata(cadata: str | bytes | None) -> str | bytes | None:
    if isinstance(cadata, bytes):
        with suppress(UnicodeDecodeError):
            text = cadata.decode("ascii")
            if "-----BEGIN CERTIFICATE-----" in text:
                return text
    return cadata


@contextmanager
def _temporary_pem_file(data: bytes) -> Iterator[str]:
    fd, name = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        yield name
    finally:
        with suppress(FileNotFoundError):
            Path(name).unlink()


def create_server_ssl_context(
    *,
    certfile: str | Path,
    keyfile: str | Path,
    cafile: str | Path | None = None,
    capath: str | Path | None = None,
    cadata: str | bytes | None = None,
    password: str | bytes | Callable[[], str | bytes] | None = None,
    verify_mode: ssl.VerifyMode = ssl.CERT_NONE,
    verify_flags: ssl.VerifyFlags = NO_VERIFY_FLAGS,
    minimum_version: ssl.TLSVersion | None = None,
    maximum_version: ssl.TLSVersion | None = None,
    alpn_protocols: tuple[str, ...] | None = None,
) -> ssl.SSLContext:
    """Build a server-side SSL context for a reloadable external listener."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(_path_string(certfile), _path_string(keyfile), password=password)
    if cafile is not None or capath is not None or cadata is not None:
        context.load_verify_locations(
            cafile=_path_string(cafile) if cafile is not None else None,
            capath=_path_string(capath) if capath is not None else None,
            cadata=_coerce_cadata(cadata),
        )
    context.verify_mode = verify_mode
    context.verify_flags |= verify_flags
    if minimum_version is not None:
        context.minimum_version = minimum_version
    if maximum_version is not None:
        context.maximum_version = maximum_version
    if alpn_protocols is not None:
        context.set_alpn_protocols(list(alpn_protocols))
    return context


@dataclass(frozen=True)
class PEMTLSMaterial:
    """PEM-encoded TLS material for building a server SSL context.

    The Python standard library requires file paths for loading the server
    certificate chain and private key. This helper writes those values to
    temporary files only while constructing the SSL context, then removes them.
    """

    cert_chain_pem: bytes
    private_key_pem: bytes
    ca_pem: str | bytes | None = None
    password: str | bytes | Callable[[], str | bytes] | None = None
    verify_mode: ssl.VerifyMode = ssl.CERT_NONE
    verify_flags: ssl.VerifyFlags = NO_VERIFY_FLAGS
    minimum_version: ssl.TLSVersion | None = None
    maximum_version: ssl.TLSVersion | None = None
    alpn_protocols: tuple[str, ...] | None = None

    def create_ssl_context(self) -> ssl.SSLContext:
        """Create a server SSL context from the PEM material."""
        with (
            _temporary_pem_file(self.cert_chain_pem) as certfile,
            _temporary_pem_file(self.private_key_pem) as keyfile,
        ):
            return create_server_ssl_context(
                certfile=certfile,
                keyfile=keyfile,
                cadata=self.ca_pem,
                password=self.password,
                verify_mode=self.verify_mode,
                verify_flags=self.verify_flags,
                minimum_version=self.minimum_version,
                maximum_version=self.maximum_version,
                alpn_protocols=self.alpn_protocols,
            )


class ReloadableExternalTLSListener:
    """TLS listener for handing accepted streams to an external aMQTT listener.

    Reloading builds a new SSL context and restarts only this accept socket.
    Connections already accepted by the broker keep running until the client or
    broker closes them.
    """

    def __init__(
        self,
        *,
        broker: Broker,
        listener_name: str,
        host: str,
        port: int,
        ssl_context_factory: SSLContextFactory,
        backlog: int = 100,
        ssl_handshake_timeout: float | None = None,
    ) -> None:
        if port < 0:
            msg = "port must be greater than or equal to 0"
            raise ValueError(msg)
        if backlog < 1:
            msg = "backlog must be greater than 0"
            raise ValueError(msg)
        self.broker = broker
        self.listener_name = listener_name
        self.host = host
        self.port = port
        self.backlog = backlog
        self.ssl_handshake_timeout = ssl_handshake_timeout
        self._ssl_context_factory = ssl_context_factory
        self._ssl_context: ssl.SSLContext | None = None
        self._server: asyncio.AbstractServer | None = None
        self._connection_tasks: set[asyncio.Task[None]] = set()
        self._reload_lock = asyncio.Lock()

    @property
    def active_connection_count(self) -> int:
        """Number of accepted MQTT connections currently handed to the broker."""
        return len(self._connection_tasks)

    @property
    def ssl_context(self) -> ssl.SSLContext | None:
        """SSL context currently used for new TLS handshakes."""
        return self._ssl_context

    @property
    def sockets(self) -> tuple[socket.socket, ...]:
        """Listening sockets owned by the external TLS listener."""
        if self._server is None or self._server.sockets is None:
            return ()
        return tuple(self._server.sockets)

    @property
    def actual_port(self) -> int | None:
        """Actual bound TCP port, useful when initialized with port 0."""
        for sock in self.sockets:
            address = sock.getsockname()
            if len(address) >= 2:
                return int(address[1])
        return None

    @property
    def is_serving(self) -> bool:
        """Whether the listener is currently accepting new connections."""
        return self._server is not None and self._server.is_serving()

    async def start(self) -> None:
        """Start accepting TLS connections for the configured external listener."""
        async with self._reload_lock:
            if self._server is not None:
                msg = "reloadable TLS listener is already started"
                raise RuntimeError(msg)
            self._validate_broker_listener()
            context = self._build_ssl_context(self._ssl_context_factory)
            server = await self._create_server(context)
            self._server = server
            self._ssl_context = context
            logger.info(
                "Reloadable external TLS listener '%s' started on %s:%s",
                self.listener_name,
                self.host,
                self.actual_port,
            )

    async def reload(self, ssl_context_factory: SSLContextFactory | None = None) -> None:
        """Reload TLS material for future handshakes without closing accepted connections."""
        async with self._reload_lock:
            if self._server is None or self._ssl_context is None:
                msg = "reloadable TLS listener is not started"
                raise RuntimeError(msg)

            next_factory = ssl_context_factory or self._ssl_context_factory
            next_context = self._build_ssl_context(next_factory)
            old_server = self._server
            old_context = self._ssl_context

            await self._close_accept_socket(old_server)
            try:
                next_server = await self._create_server(next_context)
            except Exception:
                self._server = await self._create_server(old_context)
                self._ssl_context = old_context
                logger.exception("TLS listener reload failed; restored previous listener")
                raise

            self._server = next_server
            self._ssl_context = next_context
            self._ssl_context_factory = next_factory
            logger.info(
                "Reloadable external TLS listener '%s' reloaded on %s:%s",
                self.listener_name,
                self.host,
                self.actual_port,
            )

    async def close(self) -> None:
        """Stop accepting new TLS connections.

        Accepted MQTT connections are not cancelled; they remain owned by the
        broker and continue until normal MQTT disconnect or broker shutdown.
        """
        async with self._reload_lock:
            if self._server is None:
                return
            await self._close_accept_socket(self._server)
            self._server = None
            self._ssl_context = None

    async def wait_connections_closed(self, timeout: float | None = None) -> None:
        """Wait for all accepted broker handoff tasks to complete."""
        tasks = set(self._connection_tasks)
        if not tasks:
            return
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)

    async def __aenter__(self) -> Self:
        """Start the listener when entering an async context manager."""
        await self.start()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Close the listener when exiting an async context manager."""
        await self.close()

    def _validate_broker_listener(self) -> None:
        listener = self.broker.listeners_config.get(self.listener_name)
        if listener is None:
            msg = f"Broker listener '{self.listener_name}' is not configured"
            raise ValueError(msg)
        if listener.type != ListenerType.EXTERNAL:
            msg = f"Broker listener '{self.listener_name}' must use ListenerType.EXTERNAL"
            raise ValueError(msg)
        if not self.broker.transitions.is_started():
            msg = "Broker must be started before the external TLS listener"
            raise RuntimeError(msg)
        if self.listener_name not in getattr(self.broker, "_servers", {}):
            msg = f"Broker listener '{self.listener_name}' is not active"
            raise RuntimeError(msg)

    def _build_ssl_context(self, factory: SSLContextFactory) -> ssl.SSLContext:
        context = factory()
        if not isinstance(context, ssl.SSLContext):
            msg = "ssl_context_factory must return ssl.SSLContext"
            raise TypeError(msg)
        return context

    async def _create_server(self, context: ssl.SSLContext) -> asyncio.AbstractServer:
        kwargs: dict[str, Any] = {
            "ssl": context,
            "backlog": self.backlog,
        }
        if self.ssl_handshake_timeout is not None:
            kwargs["ssl_handshake_timeout"] = self.ssl_handshake_timeout
        return await asyncio.start_server(self._client_connected, self.host, self.port, **kwargs)

    async def _close_accept_socket(self, server: asyncio.AbstractServer) -> None:
        server.close()
        await asyncio.sleep(0)

    async def _client_connected(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._connection_tasks.add(task)

        writer_adapter = StreamWriterAdapter(writer)
        try:
            await self.broker.external_connected(
                StreamReaderAdapter(reader),
                writer_adapter,
                self.listener_name,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("External TLS listener '%s' connection failed", self.listener_name)
            await writer_adapter.close()
        finally:
            if task is not None:
                self._connection_tasks.discard(task)
