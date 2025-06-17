import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
import contextlib
import copy
from functools import wraps
import logging
from pathlib import Path
import ssl
from typing import TYPE_CHECKING, Any, TypeAlias, cast
from urllib.parse import urlparse, urlunparse

import websockets
from websockets import HeadersLike, InvalidHandshake, InvalidURI

from amqtt.adapters import (
    StreamReaderAdapter,
    StreamWriterAdapter,
    WebSocketsReader,
    WebSocketsWriter,
)
from amqtt.errors import ClientError, ConnectError, ProtocolHandlerError
from amqtt.mqtt.connack import CONNECTION_ACCEPTED
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.mqtt.protocol.client_handler import ClientProtocolHandler
from amqtt.plugins.manager import BaseContext, PluginManager
from amqtt.session import ApplicationMessage, OutgoingApplicationMessage, Session
from amqtt.utils import gen_client_id, read_yaml_config

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

_defaults: dict[str, Any] | None = read_yaml_config(Path(__file__).parent / "scripts/default_client.yaml")


class ClientContext(BaseContext):
    """ClientContext is used as the context passed to plugins interacting with the client.

    It acts as an adapter to client services from plugins.
    """

    def __init__(self) -> None:
        super().__init__()
        self.config = None


base_logger = logging.getLogger(__name__)

_F: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]


def mqtt_connected(func: _F) -> _F:
    """MQTTClient coroutines decorator which will wait until connection before calling the decorated method.

    :param func: coroutine to be called once connected
    :return: coroutine result.
    """

    @wraps(func)
    async def wrapper(self: "MQTTClient", *args: Any, **kwargs: Any) -> Any:
        if not self._connected_state.is_set():
            base_logger.warning("Client not connected, waiting for it")
            _, pending = await asyncio.wait(
                [
                    asyncio.create_task(self._connected_state.wait()),
                    asyncio.create_task(self._no_more_connections.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            if self._no_more_connections.is_set():
                msg = "Will not reconnect"
                raise ClientError(msg)
        return await func(self, *args, **kwargs)

    return cast("_F", wrapper)


class MQTTClient:
    """MQTT client implementation.

    MQTTClient instances provides API for connecting to a broker and send/receive
     messages using the MQTT protocol.

    Args:
        client_id: MQTT client ID to use when connecting to the broker. If none,
            it will be generated randomly by `amqtt.utils.gen_client_id`
        config: dictionary of configuration options (see [client configuration](client_config.md)).

    Raises:
        PluginError

    """

    def __init__(self, client_id: str | None = None, config: dict[str, Any] | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = copy.deepcopy(_defaults or {})
        if config is not None:
            self.config.update(config)
        self.client_id = client_id if client_id is not None else gen_client_id()

        self.session: Session | None = None
        self._handler: ClientProtocolHandler | None = None
        self._disconnect_task: asyncio.Task[Any] | None = None
        self._connected_state = asyncio.Event()
        self._no_more_connections = asyncio.Event()
        self.additional_headers: dict[str, Any] | HeadersLike = {}

        # Init plugins manager
        context = ClientContext()
        context.config = self.config
        self.plugins_manager: PluginManager[ClientContext] = PluginManager("amqtt.client.plugins", context)
        self.client_tasks: deque[asyncio.Task[Any]] = deque()

    async def connect(
        self,
        uri: str | None = None,
        cleansession: bool | None = None,
        cafile: str | None = None,
        capath: str | None = None,
        cadata: str | None = None,
        additional_headers: dict[str, Any] | HeadersLike | None = None,
    ) -> int:
        """Connect to a remote broker.

        At first, a network connection is established with the server
        using the given protocol (``mqtt``, ``mqtts``, ``ws`` or ``wss``).
        Once the socket is connected, a
        [CONNECT](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718028>)
        message is sent with the requested information.

        Args:
            uri: Broker URI connection, conforming to
                [MQTT URI scheme](https://github.com/mqtt/mqtt.github.io/wiki/URI-Scheme). default,
                will be taken from the ``uri`` config attribute.
            cleansession: MQTT CONNECT clean session flag
            cafile: server certificate authority file (optional, used for secured connection)
            capath: server certificate authority path (optional, used for secured connection)
            cadata: server certificate authority data (optional, used for secured connection)
            additional_headers: a dictionary with additional http headers that should be sent on the
                initial connection (optional, used only with websocket connections)

        Returns:
            [CONNACK](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718033)'s return code

        Raises:
            ClientError, ConnectError

        """
        additional_headers = additional_headers if additional_headers is not None else {}
        self.session = self._init_session(uri, cleansession, cafile, capath, cadata)
        self.additional_headers = additional_headers
        self.logger.debug(f"Connecting to: {self.session.broker_uri}")

        try:
            return await self._do_connect()
        except asyncio.CancelledError as e:
            msg = "Future or Task was cancelled"
            raise ConnectError(msg) from e
        except Exception as e:
            self.logger.warning(f"Connection failed: {e!r}")
            if not self.config.get("auto_reconnect", False):
                raise
            return await self.reconnect()

    async def disconnect(self) -> None:
        """Disconnect from the connected broker.

        This method sends a [DISCONNECT](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718090)
        message and closes the network socket.

        """
        await self.cancel_tasks()

        if not (self.session and self._handler):
            self.logger.warning("Session or handler not initialized, ignoring disconnect.")
            return

        if not self.session.transitions.is_connected():
            self.logger.warning("Client session not connected, ignoring call.")
            return

        if self._disconnect_task and not self._disconnect_task.done():
            self._disconnect_task.cancel()

        await self._handler.mqtt_disconnect()
        self._connected_state.clear()
        await self._handler.stop()
        self.session.transitions.disconnect()

    async def cancel_tasks(self) -> None:
        """Cancel all pending tasks."""
        while self.client_tasks:
            task = self.client_tasks.pop()
            task.cancel()

    async def reconnect(self, cleansession: bool | None = None) -> int:
        """Reconnect a previously connected broker.

        Reconnection tries to establish a network connection
        and send a [CONNECT](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718028) message.
        Retries interval and attempts can be controlled with the ``reconnect_max_interval``
        and ``reconnect_retries`` configuration parameters.

        Args:
            cleansession: clean session flag used in MQTT CONNECT messages sent for reconnections.

        Returns:
            [CONNACK](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718033) return code

        Raises:
            amqtt.client.ConnectException: if re-connection fails after max retries.

        """
        if self.session and self.session.transitions.is_connected():
            self.logger.warning("Client already connected")
            return CONNECTION_ACCEPTED

        if self.session and cleansession:
            self.session.clean_session = cleansession
        self.logger.debug(f"Reconnecting with session parameters: {self.session}")

        reconnect_max_interval = self.config.get("reconnect_max_interval", 10)
        reconnect_retries = self.config.get("reconnect_retries", 2)
        nb_attempt = 1

        while True:
            try:
                self.logger.debug(f"Reconnect attempt {nb_attempt}...")
                return await self._do_connect()
            except asyncio.CancelledError as e:
                msg = "Future or Task was cancelled"
                raise ConnectError(msg) from e
            except Exception as e:
                self.logger.warning(f"Reconnection attempt failed: {e!r}")
                self.logger.debug("", exc_info=True)
                if 0 <= reconnect_retries < nb_attempt:
                    self.logger.exception("Maximum connection attempts reached. Reconnection aborted.")
                    self.logger.debug("", exc_info=True)
                    msg = "Too many failed attempts"
                    raise ConnectError(msg) from e
                delay = min(reconnect_max_interval, 2**nb_attempt)
                self.logger.debug(f"Waiting {delay} seconds before next attempt")
                await asyncio.sleep(delay)
                nb_attempt += 1

    async def _do_connect(self) -> int:
        return_code = await self._connect_coro()
        self._disconnect_task = asyncio.create_task(self.handle_connection_close())
        return return_code

    @mqtt_connected
    async def ping(self) -> None:
        """Ping the broker.

        Send a MQTT [PINGREQ](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718081)
        message for response.

        """
        if self.session and self._handler and self.session.transitions.is_connected():
            await self._handler.mqtt_ping()
        elif not self.session:
            self.logger.warning("Session is not initialized.")
        elif not self._handler:
            self.logger.warning("Handler is not initialized.")
        else:
            self.logger.warning(f"PING incompatible with state '{self.session.transitions.state}'")

    @mqtt_connected
    async def publish(
        self,
        topic: str,
        message: bytes,
        qos: int | None = None,
        retain: bool | None = None,
        ack_timeout: int | None = None,
    ) -> OutgoingApplicationMessage:
        """Publish a message to the broker.

        Send a MQTT [PUBLISH](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718037)
        message and wait for acknowledgment depending on Quality Of Service

        Args:
            topic: topic name to which message data is published
            message: payload message (as bytes) to send.
            qos: requested publish quality of service : QOS_0, QOS_1 or QOS_2. Defaults to `default_qos`
                config parameter or QOS_0.
            retain: retain flag. Defaults to ``default_retain`` config parameter or False.
            ack_timeout: duration to wait for connection acknowledgment from broker.

        Returns:
            the message that was sent

        """
        if self._handler is None:
            msg = "Handler is not initialized."
            raise ClientError(msg)

        def get_retain_and_qos() -> tuple[int, bool]:
            if qos is not None:
                if qos not in (QOS_0, QOS_1, QOS_2):
                    msg = f"QOS '{qos}' is not one of QOS_0, QOS_1, QOS_2."
                    raise ClientError(msg)
                _qos = qos
            else:
                _qos = self.config["default_qos"]
                with contextlib.suppress(KeyError):
                    _qos = self.config["topics"][topic]["qos"]
            if retain:
                _retain = retain
            else:
                _retain = self.config["default_retain"]
                with contextlib.suppress(KeyError):
                    _retain = self.config["topics"][topic]["retain"]
            return _qos, _retain

        (app_qos, app_retain) = get_retain_and_qos()
        return await self._handler.mqtt_publish(
            topic,
            message,
            app_qos,
            app_retain,
            ack_timeout,
        )

    @mqtt_connected
    async def subscribe(self, topics: list[tuple[str, int]]) -> list[int]:
        """Subscribe to topics.

        Send a MQTT [SUBSCRIBE](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718063)
        message and wait for broker acknowledgment.

        Args:
            topics: array of tuples containing topic pattern and QOS from `amqtt.mqtt.constants` to subscribe. For example:
                ```python
                [
                    ("$SYS/broker/uptime", QOS_1),
                    ("$SYS/broker/load/#", QOS_2),
                ]
                ```

        Returns:
            [SUBACK](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718068) message return code.

        """
        if self._handler and self.session:
            return await self._handler.mqtt_subscribe(topics, self.session.next_packet_id)
        return [0x80]

    @mqtt_connected
    async def unsubscribe(self, topics: list[str]) -> None:
        """Unsubscribe from topics.

        Send a MQTT [UNSUBSCRIBE](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718072)
        message and wait for broker [UNSUBACK](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718077)
        message.

        Args:
            topics: array of topics to unsubscribe from.
                ```
                ["$SYS/broker/uptime", "$SYS/broker/load/#"]
                ```

        """
        if self._handler and self.session:
            await self._handler.mqtt_unsubscribe(topics, self.session.next_packet_id)

    async def deliver_message(self, timeout_duration: float | None = None) -> ApplicationMessage | None:
        """Deliver the next received message.

        Deliver next message received from the broker. If no message is available, this methods waits until next message arrives
        or ``timeout_duration`` occurs.

        Args:
            timeout_duration: maximum number of seconds to wait before returning. If not specified or None, there is no limit.

        Returns:
            instance of `amqtt.session.ApplicationMessage` containing received message information flow.

        Raises:
            asyncio.TimeoutError: if timeout occurs before a message is delivered

        """
        if self._handler is None:
            msg = "Handler is not initialized."
            raise ClientError(msg)

        deliver_task = asyncio.create_task(self._handler.mqtt_deliver_next_message())
        self.client_tasks.append(deliver_task)
        self.logger.debug("Waiting for message delivery")

        done, _ = await asyncio.wait(
            [deliver_task],
            return_when=asyncio.FIRST_EXCEPTION,
            timeout=timeout_duration,
        )

        if self.client_tasks:
            self.client_tasks.pop()

        if deliver_task in done:
            exception = deliver_task.exception()
            if exception is not None:
                # deliver_task raised an exception, pass it on to our caller
                raise exception
            return deliver_task.result()
        # timeout occurred before message received
        deliver_task.cancel()
        msg = "Timeout waiting for message"
        raise asyncio.TimeoutError(msg)

    async def _connect_coro(self) -> int:
        """Perform the core connection logic."""
        if self.session is None:
            msg = "Session is not initialized."
            raise ClientError(msg)

        kwargs: dict[str, Any] = {}

        # Decode URI attributes
        uri_attributes = urlparse(self.session.broker_uri)
        scheme = uri_attributes.scheme
        secure = scheme in ("mqtts", "wss")
        self.session.username = (
            self.session.username
            if self.session.username
            else (str(uri_attributes.username) if uri_attributes.username else None)
        )
        self.session.password = (
            self.session.password
            if self.session.password
            else (str(uri_attributes.password) if uri_attributes.password else None)
        )
        self.session.remote_address = str(uri_attributes.hostname) if uri_attributes.hostname else None
        self.session.remote_port = uri_attributes.port

        if scheme in ("mqtt", "mqtts") and not self.session.remote_port:
            self.session.remote_port = 8883 if scheme == "mqtts" else 1883

        if scheme in ("ws", "wss") and not self.session.remote_port:
            self.session.remote_port = 443 if scheme == "wss" else 80

        if scheme in ("ws", "wss"):
            # Rewrite URI to conform to https://tools.ietf.org/html/rfc6455#section-3
            uri = (
                str(scheme),
                f"{self.session.remote_address}:{self.session.remote_port}",
                str(uri_attributes.path),
                str(uri_attributes.params),
                str(uri_attributes.query),
                str(uri_attributes.fragment),
            )
            self.session.broker_uri = str(urlunparse(uri))
        # Init protocol handler
        # if not self._handler:
        self._handler = ClientProtocolHandler(self.plugins_manager)

        if secure:
            sc = ssl.create_default_context(
                ssl.Purpose.SERVER_AUTH,
                cafile=self.session.cafile,
                capath=self.session.capath,
                cadata=self.session.cadata,
            )
            if "certfile" in self.config and "keyfile" in self.config:
                sc.load_cert_chain(self.config["certfile"], self.config["keyfile"])
            if "check_hostname" in self.config and isinstance(self.config["check_hostname"], bool):
                sc.check_hostname = self.config["check_hostname"]
            kwargs["ssl"] = sc

        try:
            reader: StreamReaderAdapter | WebSocketsReader | None = None
            writer: StreamWriterAdapter | WebSocketsWriter | None = None
            self._connected_state.clear()

            # Open connection
            if scheme in ("mqtt", "mqtts"):
                conn_reader, conn_writer = await asyncio.open_connection(
                    self.session.remote_address,
                    self.session.remote_port,
                    **kwargs,
                )

                reader = StreamReaderAdapter(conn_reader)
                writer = StreamWriterAdapter(conn_writer)
            elif scheme in ("ws", "wss") and self.session.broker_uri:
                websocket: ClientConnection = await websockets.connect(
                    self.session.broker_uri,
                    subprotocols=[websockets.Subprotocol("mqtt")],
                    additional_headers=self.additional_headers,
                    **kwargs,
                )
                reader = WebSocketsReader(websocket)
                writer = WebSocketsWriter(websocket)
            elif not self.session.broker_uri:
                msg = "missing broker uri"
                raise ClientError(msg)
            else:
                msg = f"incorrect scheme defined in uri: '{scheme!r}'"
                raise ClientError(msg)

            # Start MQTT protocol
            self._handler.attach(self.session, reader, writer)
            return_code: int | None = await self._handler.mqtt_connect()

            if return_code is not CONNECTION_ACCEPTED:
                self.session.transitions.disconnect()
                self.logger.warning(f"Connection rejected with code '{return_code}'")
                msg = "Connection rejected by broker"
                exc = ConnectError(msg)
                exc.return_code = return_code
                raise exc
            # Handle MQTT protocol
            await self._handler.start()
            self.session.transitions.connect()
            self._connected_state.set()
            self.logger.debug(f"Connected to {self.session.remote_address}:{self.session.remote_port}")

        except (InvalidURI, InvalidHandshake, ProtocolHandlerError, ConnectionError, OSError) as e:
            self.logger.debug(f"Connection failed : {self.session.broker_uri} [{e!r}]")
            self.session.transitions.disconnect()
            raise ConnectError(e) from e
        return return_code

    async def handle_connection_close(self) -> None:
        """Handle disconnection from the broker."""
        if self.session is None:
            msg = "Session is not initialized."
            raise ClientError(msg)
        if self._handler is None:
            msg = "Handler is not initialized."
            raise ClientError(msg)

        def cancel_tasks() -> None:
            self._no_more_connections.set()
            while self.client_tasks:
                task = self.client_tasks.popleft()
                if not task.done():
                    task.cancel(msg="Connection closed.")

        self.logger.debug("Monitoring broker disconnection")
        # Wait for disconnection from broker (like connection lost)
        await self._handler.wait_disconnect()
        self.logger.warning("Disconnected from broker")

        # Block client API
        self._connected_state.clear()

        # stop an clean handler
        await self._handler.stop()
        self._handler.detach()
        self.session.transitions.disconnect()

        if self.config.get("auto_reconnect", False):
            # Try reconnection
            self.logger.debug("Auto-reconnecting")
            try:
                await self.reconnect()
            except ConnectError:
                # Cancel client pending tasks
                cancel_tasks()
        else:
            # Cancel client pending tasks
            cancel_tasks()

    def _init_session(
        self,
        uri: str | None = None,
        cleansession: bool | None = None,
        cafile: str | None = None,
        capath: str | None = None,
        cadata: str | None = None,
    ) -> Session:
        """Initialize the MQTT session."""
        broker_conf = self.config.get("broker", {}).copy()
        broker_conf.update(
            {k: v for k, v in {"uri": uri, "cafile": cafile, "capath": capath, "cadata": cadata}.items() if v is not None},
        )

        if not broker_conf.get("uri"):
            msg = "Missing connection parameter 'uri'"
            raise ClientError(msg)

        session = Session()
        session.broker_uri = broker_conf["uri"]
        session.client_id = self.client_id
        session.cafile = broker_conf.get("cafile")
        session.capath = broker_conf.get("capath")
        session.cadata = broker_conf.get("cadata")

        if cleansession is not None:
            broker_conf["cleansession"] = cleansession
            session.clean_session = cleansession
        else:
            session.clean_session = self.config.get("cleansession", True)

        session.keep_alive = self.config["keep_alive"] - self.config["ping_delay"]

        if "will" in self.config:
            session.will_flag = True
            session.will_retain = self.config["will"]["retain"]
            session.will_topic = self.config["will"]["topic"]
            session.will_message = self.config["will"]["message"].encode()
            session.will_qos = self.config["will"]["qos"]

        return session
