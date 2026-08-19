"""Reloadable TLS listener support for external broker listeners."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import ssl
from typing import TYPE_CHECKING, Any
from typing_extensions import Self

from amqtt.adapters import StreamReaderAdapter, StreamWriterAdapter
from amqtt.contexts import ListenerType
from amqtt.errors import BrokerError, ProtocolHandlerError

if TYPE_CHECKING:
    import socket

    from amqtt.broker import Broker

logger = logging.getLogger(__name__)

SSLContextFactory = Callable[[], ssl.SSLContext]


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
        self._server: asyncio.Server | None = None
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
        context: object = factory()
        if not isinstance(context, ssl.SSLContext):
            msg = "ssl_context_factory must return ssl.SSLContext"
            raise TypeError(msg)
        return context

    async def _create_server(self, context: ssl.SSLContext) -> asyncio.Server:
        kwargs: dict[str, Any] = {
            "ssl": context,
            "backlog": self.backlog,
        }
        if self.ssl_handshake_timeout is not None:
            kwargs["ssl_handshake_timeout"] = self.ssl_handshake_timeout
        return await asyncio.start_server(self._client_connected, self.host, self.port, **kwargs)

    async def _close_accept_socket(self, server: asyncio.Server) -> None:
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
        except (BrokerError, ProtocolHandlerError, ssl.SSLError, OSError, ConnectionError, TimeoutError):
            logger.warning("External TLS listener '%s' connection failed", self.listener_name)
            await writer_adapter.close()
        finally:
            if task is not None:
                self._connection_tasks.discard(task)
