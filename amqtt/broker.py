import asyncio
from asyncio import CancelledError, futures
from collections import deque
from collections.abc import Generator
import copy
from enum import Enum
from functools import partial
import logging
from pathlib import Path
import re
import ssl
from typing import Any, ClassVar, TypeAlias

from transitions import Machine, MachineError
import websockets.asyncio.server
from websockets.asyncio.server import ServerConnection

from amqtt.adapters import (
    ReaderAdapter,
    StreamReaderAdapter,
    StreamWriterAdapter,
    WebSocketsReader,
    WebSocketsWriter,
    WriterAdapter,
)
from amqtt.errors import AMQTTError, BrokerError, MQTTError, NoDataError
from amqtt.mqtt.protocol.broker_handler import BrokerProtocolHandler
from amqtt.session import ApplicationMessage, OutgoingApplicationMessage, Session
from amqtt.utils import format_client_message, gen_client_id, read_yaml_config

from .events import BrokerEvents
from .mqtt.disconnect import DisconnectPacket
from .plugins.manager import BaseContext, PluginManager

_CONFIG_LISTENER: TypeAlias = dict[str, int | bool | dict[str, Any]]
_BROADCAST: TypeAlias = dict[str, Session | str | bytes | bytearray | int | None]


_defaults = read_yaml_config(Path(__file__).parent / "scripts/default_broker.yaml")


# Default port numbers
DEFAULT_PORTS = {"tcp": 1883, "ws": 8883}
AMQTT_MAGIC_VALUE_RET_SUBSCRIBED = 0x80


class Action(Enum):
    """Actions issued by the broker."""

    SUBSCRIBE = "subscribe"
    PUBLISH = "publish"


class RetainedApplicationMessage(ApplicationMessage):
    __slots__ = ("data", "qos", "source_session", "topic")

    def __init__(self, source_session: Session | None, topic: str, data: bytes | bytearray, qos: int | None = None) -> None:
        super().__init__(None, topic, qos, data, retain=True)
        self.source_session = source_session
        self.topic = topic
        self.data = data
        self.qos = qos


class Server:
    def __init__(
        self,
        listener_name: str,
        server_instance: asyncio.Server | websockets.asyncio.server.Server,
        max_connections: int = -1,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.instance = server_instance
        self.conn_count = 0
        self.listener_name = listener_name
        self.max_connections = max_connections
        self.semaphore = asyncio.Semaphore(max_connections) if max_connections > 0 else None

    async def acquire_connection(self) -> None:
        if self.semaphore:
            await self.semaphore.acquire()
        self.conn_count += 1
        self.logger.info(
            f"Listener '{self.listener_name}': {self.conn_count}/"
            f"{self.max_connections if self.max_connections > 0 else '∞'} connections acquired",
        )

    def release_connection(self) -> None:
        if self.semaphore:
            self.semaphore.release()
        self.conn_count -= 1
        self.logger.info(
            f"Listener '{self.listener_name}': {self.conn_count}/"
            f"{self.max_connections if self.max_connections > 0 else '∞'} connections acquired",
        )

    async def close_instance(self) -> None:
        if self.instance:
            self.instance.close()
            await self.instance.wait_closed()


class BrokerContext(BaseContext):
    """BrokerContext is used as the context passed to plugins interacting with the broker.

    It act as an adapter to broker services from plugins developed for HBMQTT broker.
    """

    def __init__(self, broker: "Broker") -> None:
        super().__init__()
        self.config: _CONFIG_LISTENER | None = None
        self._broker_instance = broker

    async def broadcast_message(self, topic: str, data: bytes, qos: int | None = None) -> None:
        await self._broker_instance.internal_message_broadcast(topic, data, qos)

    def retain_message(self, topic_name: str, data: bytes | bytearray, qos: int | None = None) -> None:
        self._broker_instance.retain_message(None, topic_name, data, qos)

    @property
    def sessions(self) -> Generator[Session]:
        for session in self._broker_instance.sessions.values():
            yield session[0]

    @property
    def retained_messages(self) -> dict[str, RetainedApplicationMessage]:
        return self._broker_instance.retained_messages

    @property
    def subscriptions(self) -> dict[str, list[tuple[Session, int]]]:
        return self._broker_instance.subscriptions


class Broker:
    """MQTT 3.1.1 compliant broker implementation.

    Args:
        config: dictionary of configuration options (see [broker configuration](broker_config.md)).
        loop: asyncio loop. defaults to `asyncio.new_event_loop()`.
        plugin_namespace: plugin namespace to use when loading plugin entry_points. defaults to `amqtt.broker.plugins`.

    Raises:
        BrokerError, ParserError, PluginError

    """

    states: ClassVar[list[str]] = [
        "new",
        "starting",
        "started",
        "not_started",
        "stopping",
        "stopped",
        "not_stopped",
    ]

    def __init__(
        self,
        config: _CONFIG_LISTENER | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        plugin_namespace: str | None = None,
    ) -> None:
        """Initialize the broker."""
        self.logger = logging.getLogger(__name__)
        self.config = copy.deepcopy(_defaults or {})
        if config is not None:
            self.config.update(config)
        self._build_listeners_config(self.config)

        self._loop = loop or asyncio.get_running_loop()
        self._servers: dict[str, Server] = {}
        self._init_states()
        self._sessions: dict[str, tuple[Session, BrokerProtocolHandler]] = {}
        self._subscriptions: dict[str, list[tuple[Session, int]]] = {}
        self._retained_messages: dict[str, RetainedApplicationMessage] = {}

        # Broadcast queue for outgoing messages
        self._broadcast_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._broadcast_task: asyncio.Task[Any] | None = None
        self._broadcast_shutdown_waiter: asyncio.Future[Any] = futures.Future()

        # Tasks queue for managing broadcasting tasks
        self._tasks_queue: deque[asyncio.Task[OutgoingApplicationMessage]] = deque()

        # Initialize plugins manager

        context = BrokerContext(self)
        context.config = self.config
        namespace = plugin_namespace or "amqtt.broker.plugins"
        self.plugins_manager = PluginManager(namespace, context, self._loop)

    def _build_listeners_config(self, broker_config: _CONFIG_LISTENER) -> None:
        self.listeners_config = {}
        try:
            listeners_config = broker_config.get("listeners")
            if not isinstance(listeners_config, dict):
                msg = "Listener config not found or invalid"
                raise BrokerError(msg)
            defaults = listeners_config.get("default")
            if defaults is None:
                msg = "Listener config has not default included or is invalid"
                raise BrokerError(msg)

            for listener_name, listener_conf in listeners_config.items():
                config = defaults.copy()
                config.update(listener_conf)
                self.listeners_config[listener_name] = config
        except KeyError as ke:
            msg = f"Listener config not found or invalid: {ke}"
            raise BrokerError(msg) from ke

    def _init_states(self) -> None:
        self.transitions = Machine(states=Broker.states, initial="new")
        self.transitions.add_transition(trigger="start", source="new", dest="starting", before=self._log_state_change)
        self.transitions.add_transition(trigger="starting_fail", source="starting", dest="not_started")
        self.transitions.add_transition(trigger="starting_success", source="starting", dest="started")
        self.transitions.add_transition(trigger="shutdown", source="started", dest="stopping")
        self.transitions.add_transition(trigger="stopping_success", source="stopping", dest="stopped")
        self.transitions.add_transition(trigger="stopping_failure", source="stopping", dest="not_stopped")
        self.transitions.add_transition(trigger="start", source="stopped", dest="starting")

    def _log_state_change(self) -> None:
        self.logger.debug(f"State transition: {self.transitions.state}")

    async def start(self) -> None:
        """Start the broker to serve with the given configuration.

        Start method opens network sockets and will start listening for incoming connections.
        """
        try:
            self._sessions.clear()
            self._subscriptions.clear()
            self._retained_messages.clear()
            self.transitions.start()
            self.logger.debug("Broker starting")
        except (MachineError, ValueError) as exc:
            # Backwards compat: MachineError is raised by transitions < 0.5.0.
            self.logger.warning(f"[WARN-0001] Invalid method call at this moment: {exc}")
            msg = f"Broker instance can't be started: {exc}"
            raise BrokerError(msg) from exc

        await self.plugins_manager.fire_event(BrokerEvents.PRE_START)
        try:
            await self._start_listeners()
            self.transitions.starting_success()
            await self.plugins_manager.fire_event(BrokerEvents.POST_START)
            self._broadcast_task = asyncio.ensure_future(self._broadcast_loop())
            self.logger.debug("Broker started")
        except Exception as e:
            self.logger.exception("Broker startup failed")
            self.transitions.starting_fail()
            msg = f"Broker instance can't be started: {e}"
            raise BrokerError(msg) from e

    async def _start_listeners(self) -> None:
        """Start network listeners based on the configuration."""
        for listener_name, listener in self.listeners_config.items():
            if "bind" not in listener:
                self.logger.debug(f"Listener configuration '{listener_name}' is not bound")
                continue

            max_connections = listener.get("max_connections", -1)
            ssl_context = self._create_ssl_context(listener) if listener.get("ssl", False) else None

            try:
                address, port = self._split_bindaddr_port(listener["bind"], DEFAULT_PORTS[listener["type"]])
            except ValueError as e:
                msg = f"Invalid port value in bind value: {listener['bind']}"
                raise BrokerError(msg) from e

            instance = await self._create_server_instance(listener_name, listener["type"], address, port, ssl_context)
            self._servers[listener_name] = Server(listener_name, instance, max_connections)

            self.logger.info(f"Listener '{listener_name}' bind to {listener['bind']} (max_connections={max_connections})")

    def _create_ssl_context(self, listener: dict[str, Any]) -> ssl.SSLContext:
        """Create an SSL context for a listener."""
        try:
            ssl_context = ssl.create_default_context(
                ssl.Purpose.CLIENT_AUTH,
                cafile=listener.get("cafile"),
                capath=listener.get("capath"),
                cadata=listener.get("cadata"),
            )
            ssl_context.load_cert_chain(listener["certfile"], listener["keyfile"])
            ssl_context.verify_mode = ssl.CERT_OPTIONAL
        except KeyError as ke:
            msg = f"'certfile' or 'keyfile' configuration parameter missing: {ke}"
            raise BrokerError(msg) from ke
        except FileNotFoundError as fnfe:
            msg = f"Can't read cert files '{listener['certfile']}' or '{listener['keyfile']}' : {fnfe}"
            raise BrokerError(msg) from fnfe
        return ssl_context

    async def _create_server_instance(
        self,
        listener_name: str,
        listener_type: str,
        address: str | None,
        port: int,
        ssl_context: ssl.SSLContext | None,
    ) -> asyncio.Server | websockets.asyncio.server.Server:
        """Create a server instance for a listener."""
        if listener_type == "tcp":
            return await asyncio.start_server(
                partial(self.stream_connected, listener_name=listener_name),
                address,
                port,
                reuse_address=True,
                ssl=ssl_context,
            )
        if listener_type == "ws":
            return await websockets.serve(
                partial(self.ws_connected, listener_name=listener_name),
                address,
                port,
                ssl=ssl_context,
                subprotocols=[websockets.Subprotocol("mqtt")],
            )
        msg = f"Unsupported listener type: {listener_type}"
        raise BrokerError(msg)

    async def shutdown(self) -> None:
        """Stop broker instance."""
        self.logger.info("Shutting down broker...")
        # Fire broker_shutdown event to plugins
        await self.plugins_manager.fire_event(BrokerEvents.PRE_SHUTDOWN)

        # Cleanup all sessions
        for client_id in list(self._sessions.keys()):
            await self._cleanup_session(client_id)

        # Clear retained messages
        self.logger.debug(f"Clearing {len(self._retained_messages)} retained messages")
        self._retained_messages.clear()

        self.transitions.shutdown()

        await self._shutdown_broadcast_loop()

        for server in self._servers.values():
            await server.close_instance()

        if not self._broadcast_queue.empty():
            self.logger.warning(f"{self._broadcast_queue.qsize()} messages not broadcasted")
            # Clear the broadcast queue
            while not self._broadcast_queue.empty():
                self._broadcast_queue.get_nowait()

        self.logger.info("Broker closed")
        await self.plugins_manager.fire_event(BrokerEvents.POST_SHUTDOWN)
        self.transitions.stopping_success()

    async def _cleanup_session(self, client_id: str) -> None:
        """Centralized cleanup logic for a session."""
        session, handler = self._sessions.pop(client_id, (None, None))

        if handler:
            self.logger.debug(f"Stopping handler for session {client_id}")
            await self._stop_handler(handler)
        if session:
            self.logger.debug(f"Clearing all subscriptions for session {client_id}")
            await self._del_all_subscriptions(session)
            session.clear_queues()

    async def internal_message_broadcast(self, topic: str, data: bytes, qos: int | None = None) -> None:
        return await self._broadcast_message(None, topic, data, qos)

    async def ws_connected(self, websocket: ServerConnection, listener_name: str) -> None:
        await self._client_connected(listener_name, WebSocketsReader(websocket), WebSocketsWriter(websocket))

    async def stream_connected(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, listener_name: str) -> None:
        await self._client_connected(listener_name, StreamReaderAdapter(reader), StreamWriterAdapter(writer))

    async def _client_connected(self, listener_name: str, reader: ReaderAdapter, writer: WriterAdapter) -> None:
        """Handle a new client connection."""
        server = self._servers.get(listener_name)
        if not server:
            msg = f"Invalid listener name '{listener_name}'"
            raise BrokerError(msg)

        await server.acquire_connection()
        remote_info = writer.get_peer_info()
        if remote_info is None:
            self.logger.warning("Remote info could not be retrieved from peer info")
            return

        remote_address, remote_port = remote_info
        self.logger.info(f"Connection from {remote_address}:{remote_port} on listener '{listener_name}'")

        try:
            handler, client_session = await self._initialize_client_session(reader, writer, remote_address, remote_port)
        except (AMQTTError, MQTTError, NoDataError) as exc:
            self.logger.warning(f"Failed to initialize client session: {exc}")
            server.release_connection()
            return

        try:
            await self._handle_client_session(reader, writer, client_session, handler, server, listener_name)
        except (AMQTTError, MQTTError, NoDataError) as exc:
            self.logger.warning(f"Error while handling client session: {exc}")
        finally:
            self.logger.debug(f"{client_session.client_id} Client disconnected")
            server.release_connection()

    async def _initialize_client_session(
        self,
        reader: ReaderAdapter,
        writer: WriterAdapter,
        remote_address: str,
        remote_port: int,
    ) -> tuple[BrokerProtocolHandler, Session]:
        """Initialize a client session and protocol handler."""
        # Wait for first packet and expect a CONNECT
        try:
            handler, client_session = await BrokerProtocolHandler.init_from_connect(reader, writer, self.plugins_manager)
        except AMQTTError as exc:
            self.logger.warning(
                f"[MQTT-3.1.0-1] {format_client_message(address=remote_address, port=remote_port)}:"
                f" Can't read first packet as CONNECT: {exc}",
            )
            raise AMQTTError(exc) from exc
        except MQTTError as exc:
            self.logger.exception(
                f"Invalid connection from {format_client_message(address=remote_address, port=remote_port)}",
            )
            await writer.close()
            raise MQTTError(exc) from exc
        except NoDataError as exc:
            self.logger.error(  # noqa: TRY400
                f"No data from {format_client_message(address=remote_address, port=remote_port)} : {exc}",
            )
            raise AMQTTError(exc) from exc

        if client_session.clean_session:
            # Delete existing session and create a new one
            if client_session.client_id is not None and client_session.client_id != "":
                await self._delete_session(client_session.client_id)
            else:
                client_session.client_id = gen_client_id()
            client_session.parent = 0
        # Get session from cache
        elif client_session.client_id in self._sessions:
            self.logger.debug(f"Found old session {self._sessions[client_session.client_id]!r}")
            client_session, _ = self._sessions[client_session.client_id]
            client_session.parent = 1
        else:
            client_session.parent = 0

        timeout_disconnect_delay = self.config.get("timeout-disconnect-delay", 0)
        if client_session.keep_alive > 0 and isinstance(timeout_disconnect_delay, int):
            client_session.keep_alive += timeout_disconnect_delay

        self.logger.debug(f"Keep-alive timeout={client_session.keep_alive}")
        return handler, client_session

    async def _handle_client_session(
        self,
        reader: ReaderAdapter,
        writer: WriterAdapter,
        client_session: Session,
        handler: BrokerProtocolHandler,
        server: Server,
        listener_name: str,
    ) -> None:
        """Handle the lifecycle of a client session."""
        authenticated = await self._authenticate(client_session, self.listeners_config[listener_name])
        if not authenticated:
            await writer.close()
            return

        if client_session.client_id is None:
            msg = "Client ID was not correctly created/set."
            raise BrokerError(msg)

        while True:
            try:
                client_session.transitions.connect()
                break
            except (MachineError, ValueError):
                if client_session.transitions.is_connected():
                    self.logger.warning(f"Client {client_session.client_id} is already connected, performing take-over.")
                    old_session = self._sessions[client_session.client_id]
                    await old_session[1].handle_connection_closed()
                    await old_session[1].stop()
                    break
                self.logger.warning(f"Client {client_session.client_id} is reconnecting too quickly, make it wait")
                await asyncio.sleep(1)

        handler.attach(client_session, reader, writer)
        self._sessions[client_session.client_id] = (client_session, handler)

        await handler.mqtt_connack_authorize(authenticated)
        await self.plugins_manager.fire_event(BrokerEvents.CLIENT_CONNECTED, client_id=client_session.client_id)

        self.logger.debug(f"{client_session.client_id} Start messages handling")
        await handler.start()
        self.logger.debug(f"Retained messages queue size: {client_session.retained_messages.qsize()}")
        await self._publish_session_retained_messages(client_session)

        await self._client_message_loop(client_session, handler)

    async def _client_message_loop(self, client_session: Session, handler: BrokerProtocolHandler) -> None:
        """Run the main loop to handle client messages."""
        # Init and start loop for handling client messages (publish, subscribe/unsubscribe, disconnect)
        disconnect_waiter = asyncio.ensure_future(handler.wait_disconnect())
        subscribe_waiter = asyncio.ensure_future(handler.get_next_pending_subscription())
        unsubscribe_waiter = asyncio.ensure_future(handler.get_next_pending_unsubscription())
        wait_deliver = asyncio.ensure_future(handler.mqtt_deliver_next_message())
        connected = True

        while connected:
            try:
                done, _ = await asyncio.wait(
                    [
                        disconnect_waiter,
                        subscribe_waiter,
                        unsubscribe_waiter,
                        wait_deliver,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if disconnect_waiter in done:
                    # handle the disconnection: normal or abnormal result, either way, the client is no longer connected
                    await self._handle_disconnect(client_session, handler, disconnect_waiter)
                    connected = False

                    # no need to reschedule the `disconnect_waiter` since we're exiting the message loop


                if subscribe_waiter in done:
                    await self._handle_subscription(client_session, handler, subscribe_waiter)
                    subscribe_waiter = asyncio.ensure_future(handler.get_next_pending_subscription())
                    self.logger.debug(repr(self._subscriptions))

                if unsubscribe_waiter in done:
                    await self._handle_unsubscription(client_session, handler, unsubscribe_waiter)
                    unsubscribe_waiter = asyncio.ensure_future(handler.get_next_pending_unsubscription())

                if wait_deliver in done:
                    if not await self._handle_message_delivery(client_session, handler, wait_deliver):
                        break
                    wait_deliver = asyncio.ensure_future(handler.mqtt_deliver_next_message())

            except asyncio.CancelledError:
                self.logger.debug("Client loop cancelled")
                break

        disconnect_waiter.cancel()
        subscribe_waiter.cancel()
        unsubscribe_waiter.cancel()
        wait_deliver.cancel()

    async def _handle_disconnect(
        self,
        client_session: Session,
        handler: BrokerProtocolHandler,
        disconnect_waiter: asyncio.Future[Any],
    ) -> None:
        """Handle client disconnection.

        Args:
            client_session (Session): client session
            handler (BrokerProtocolHandler): broker protocol handler
            disconnect_waiter (asyncio.Future[Any]): future to wait for disconnection

        """
        # check the disconnected waiter result
        result = disconnect_waiter.result()
        self.logger.debug(f"{client_session.client_id} Result from wait_disconnect: {result}")
        # if the client disconnects abruptly by sending no message or the message isn't a disconnect packet
        if result is None or not isinstance(result, DisconnectPacket):
            self.logger.debug(f"Will flag: {client_session.will_flag}")
            if client_session.will_flag:
                self.logger.debug(
                    f"Client {format_client_message(client_session)} disconnected abnormally, sending will message",
                )
                await self._broadcast_message(
                    client_session,
                    client_session.will_topic,
                    client_session.will_message,
                    client_session.will_qos,
                )
                if client_session.will_retain:
                    self.retain_message(
                        client_session,
                        client_session.will_topic,
                        client_session.will_message,
                        client_session.will_qos,
                    )

        # normal or not, let's end the client's session
        self.logger.debug(f"{client_session.client_id} Disconnecting session")
        await self._stop_handler(handler)
        client_session.transitions.disconnect()
        await self.plugins_manager.fire_event(BrokerEvents.CLIENT_DISCONNECTED, client_id=client_session.client_id)


    async def _handle_subscription(
        self,
        client_session: Session,
        handler: BrokerProtocolHandler,
        subscribe_waiter: asyncio.Future[Any],
    ) -> None:
        """Handle client subscription."""
        self.logger.debug(f"{client_session.client_id} handling subscription")
        subscriptions = subscribe_waiter.result()
        return_codes = [await self._add_subscription(subscription, client_session) for subscription in subscriptions.topics]
        await handler.mqtt_acknowledge_subscription(subscriptions.packet_id, return_codes)
        for index, subscription in enumerate(subscriptions.topics):
            if return_codes[index] != AMQTT_MAGIC_VALUE_RET_SUBSCRIBED:
                await self.plugins_manager.fire_event(
                    BrokerEvents.CLIENT_SUBSCRIBED,
                    client_id=client_session.client_id,
                    topic=subscription[0],
                    qos=subscription[1],
                )
                await self._publish_retained_messages_for_subscription(subscription, client_session)

    async def _handle_unsubscription(
        self,
        client_session: Session,
        handler: BrokerProtocolHandler,
        unsubscribe_waiter: asyncio.Future[Any],
    ) -> None:
        """Handle client unsubscription."""
        self.logger.debug(f"{client_session.client_id} handling unsubscription")
        unsubscription = unsubscribe_waiter.result()
        for topic in unsubscription.topics:
            self._del_subscription(topic, client_session)
            await self.plugins_manager.fire_event(
                BrokerEvents.CLIENT_UNSUBSCRIBED,
                client_id=client_session.client_id,
                topic=topic,
            )
        await handler.mqtt_acknowledge_unsubscription(unsubscription.packet_id)

    async def _handle_message_delivery(
        self,
        client_session: Session,
        handler: BrokerProtocolHandler,
        wait_deliver: asyncio.Future[Any],
    ) -> bool:
        """Handle message delivery to the client."""
        self.logger.debug(f"{client_session.client_id} handling message delivery")
        app_message = wait_deliver.result()

        if app_message is None:
            self.logger.debug("app_message was empty!")
            return True
        if not app_message.topic:
            self.logger.warning(
                f"[MQTT-4.7.3-1] - {client_session.client_id} invalid TOPIC sent in PUBLISH message, closing connection",
            )
            return False
        if "#" in app_message.topic or "+" in app_message.topic:
            self.logger.warning(
                f"[MQTT-3.3.2-2] - {client_session.client_id} invalid TOPIC sent in PUBLISH message, closing connection",
            )
            return False

        permitted = await self._topic_filtering(client_session, topic=app_message.topic, action=Action.PUBLISH)
        if not permitted:
            self.logger.info(f"{client_session.client_id} forbidden TOPIC {app_message.topic} sent in PUBLISH message.")
        else:
            await self.plugins_manager.fire_event(
                BrokerEvents.MESSAGE_RECEIVED,
                client_id=client_session.client_id,
                message=app_message,
            )
            await self._broadcast_message(client_session, app_message.topic, app_message.data)
            if app_message.publish_packet and app_message.publish_packet.retain_flag:
                self.retain_message(client_session, app_message.topic, app_message.data, app_message.qos)
        return True

    async def _init_handler(self, session: Session, reader: ReaderAdapter, writer: WriterAdapter) -> BrokerProtocolHandler:
        """Create a BrokerProtocolHandler and attach to a session."""
        handler = BrokerProtocolHandler(self.plugins_manager, loop=self._loop)
        handler.attach(session, reader, writer)
        return handler

    async def _stop_handler(self, handler: BrokerProtocolHandler) -> None:
        """Stop a running handler and detach if from the session."""
        try:
            await handler.stop()
        except Exception:
            self.logger.exception("Failed to stop handler")

    async def _authenticate(self, session: Session, _: dict[str, Any]) -> bool:
        """Call the authenticate method on registered plugins to test user authentication.

        User is considered authenticated if all plugins called returns True.
        Plugins authenticate() method are supposed to return :
         - True if user is authentication succeed
         - False if user authentication fails
         - None if authentication can't be achieved (then plugin result is then ignored)
        :param session:
        :return:
        """
        returns = await self.plugins_manager.map_plugin_auth(session=session)
        auth_result = True
        if returns:
            for plugin in returns:
                res = returns[plugin]
                if res is False:
                    auth_result = False
                    self.logger.debug(f"Authentication failed due to '{plugin.__class__}' plugin result: {res}")
                else:
                    self.logger.debug(f"'{plugin.__class__}' plugin result: {res}")
        # If all plugins returned True, authentication is success
        return auth_result

    def retain_message(
        self,
        source_session: Session | None,
        topic_name: str | None,
        data: bytes | bytearray | None,
        qos: int | None = None,
    ) -> None:
        if data and topic_name is not None:
            # If retained flag set, store the message for further subscriptions
            self.logger.debug(f"Retaining message on topic {topic_name}")
            self._retained_messages[topic_name] = RetainedApplicationMessage(source_session, topic_name, data, qos)
        # [MQTT-3.3.1-10]
        elif topic_name in self._retained_messages:
            self.logger.debug(f"Clearing retained messages for topic '{topic_name}'")
            del self._retained_messages[topic_name]

    async def _add_subscription(self, subscription: tuple[str, int], session: Session) -> int:
        topic_filter, qos = subscription
        if "#" in topic_filter and not topic_filter.endswith("#"):
            # [MQTT-4.7.1-2] Wildcard character '#' is only allowed as last character in filter
            return 0x80
        if topic_filter != "+" and "+" in topic_filter and ("/+" not in topic_filter and "+/" not in topic_filter):
            # [MQTT-4.7.1-3] + wildcard character must occupy entire level
            return 0x80
        # Check if the client is authorised to connect to the topic
        if not await self._topic_filtering(session, topic_filter, Action.SUBSCRIBE):
            return 0x80

        # Ensure "max-qos" is an integer before using it
        max_qos = self.config.get("max-qos", qos)
        if not isinstance(max_qos, int):
            max_qos = qos

        qos = min(qos, max_qos)
        if topic_filter not in self._subscriptions:
            self._subscriptions[topic_filter] = []
        if all(s.client_id != session.client_id for s, _ in self._subscriptions[topic_filter]):
            self._subscriptions[topic_filter].append((session, qos))
        else:
            self.logger.debug(f"Client {format_client_message(session=session)} has already subscribed to {topic_filter}")
        return qos

    async def _topic_filtering(self, session: Session, topic: str, action: Action) -> bool:
        """Call the topic_filtering method on registered plugins to check that the subscription is allowed.

        User is considered allowed if all plugins called return True.
        Plugins topic_filtering() method are supposed to return :
         - True if MQTT client can be subscribed to the topic
         - False if MQTT client is not allowed to subscribe to the topic
         - None if topic filtering can't be achieved (then plugin result is then ignored)
        :param session:
        :param topic: Topic in which the client wants to subscribe / publish
        :param action: What is being done with the topic?  subscribe or publish
        :return:
        """
        topic_config = self.config.get("topic-check", {})
        enabled = False

        if isinstance(topic_config, dict):
            enabled = topic_config.get("enabled", False)

        if not enabled:
            return True

        results = await self.plugins_manager.map_plugin_topic(session=session, topic=topic, action=action)
        return all(result for result in results.values())

    async def _delete_session(self, client_id: str) -> None:
        """Delete an existing session data, for example due to clean session set in CONNECT."""
        session = self._sessions.pop(client_id, (None, None))[0]

        if session is None:
            self.logger.debug(f"Delete session : session {client_id} doesn't exist")
            return
        self.logger.debug(f"Deleted existing session {session!r}")

        # Delete subscriptions
        self.logger.debug(f"Deleting session {session!r} subscriptions")
        await self._del_all_subscriptions(session)
        session.clear_queues()

    async def _del_all_subscriptions(self, session: Session) -> None:
        """Delete all topic subscriptions for a given session."""
        filter_queue: deque[str] = deque()
        for topic in self._subscriptions:
            if self._del_subscription(topic, session):
                filter_queue.append(topic)
        for topic in filter_queue:
            if not self._subscriptions[topic]:
                del self._subscriptions[topic]

    def _del_subscription(self, a_filter: str, session: Session) -> int:
        """Delete a session subscription on a given topic.

        :param a_filter: The topic filter for the subscription.
        :param session: The session to be unsubscribed.
        :return: The number of deleted subscriptions (0 or 1).
        """
        deleted = 0
        try:
            subscriptions = self._subscriptions[a_filter]
            for index, (sub_session, _qos) in enumerate(subscriptions):
                if sub_session.client_id == session.client_id:
                    self.logger.debug(
                        f"Removing subscription on topic '{a_filter}' for client {format_client_message(session=session)}",
                    )
                    subscriptions.pop(index)
                    deleted += 1
                    break
        except KeyError:
            self.logger.debug(f"Unsubscription on topic '{a_filter}' for client {format_client_message(session=session)}")

        return deleted

    async def _broadcast_loop(self) -> None:
        """Run the main loop to broadcast messages."""
        running_tasks: deque[asyncio.Task[OutgoingApplicationMessage]] = self._tasks_queue

        try:
            while True:
                while running_tasks and running_tasks[0].done():
                    task = running_tasks.popleft()
                    try:
                        task.result()
                    except CancelledError:
                        self.logger.info(f"Task has been cancelled: {task}")
                    except Exception:
                        self.logger.exception(f"Task failed and will be skipped: {task}")

                run_broadcast_task = asyncio.ensure_future(self._run_broadcast(running_tasks))

                completed, _ = await asyncio.wait(
                    [run_broadcast_task, self._broadcast_shutdown_waiter],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Shutdown has been triggered by the broker, so stop the loop execution
                if self._broadcast_shutdown_waiter in completed:
                    run_broadcast_task.cancel()
                    break

        except BaseException:
            self.logger.exception("Broadcast loop stopped by exception")
            raise
        finally:
            # Wait until current broadcasting tasks end
            if running_tasks:
                await asyncio.gather(*running_tasks)

    async def _run_broadcast(self, running_tasks: deque[asyncio.Task[OutgoingApplicationMessage]]) -> None:
        """Process a single broadcast message."""
        broadcast = await self._broadcast_queue.get()

        self.logger.debug(f"Processing broadcast message: {broadcast}")

        for k_filter, subscriptions in self._subscriptions.items():
            if broadcast["topic"].startswith("$") and (k_filter.startswith(("+", "#"))):
                self.logger.debug("[MQTT-4.7.2-1] - ignoring broadcasting $ topic to subscriptions starting with + or #")
                continue

            # Skip all subscriptions which do not match the topic
            if not self._matches(broadcast["topic"], k_filter):
                self.logger.debug(f"Topic '{broadcast['topic']}' does not match filter '{k_filter}'")
                continue

            for target_session, sub_qos in subscriptions:
                qos = broadcast.get("qos", sub_qos)

                # Retain all messages which cannot be broadcasted, due to the session not being connected
                if target_session.transitions.state != "connected":
                    self.logger.debug(f"Session {target_session.client_id} is not connected, retaining message.")
                    await self._retain_broadcast_message(broadcast, qos, target_session)
                    continue

                self.logger.debug(
                    f"Broadcasting message from {format_client_message(session=broadcast['session'])}"
                    f" on topic '{broadcast['topic']}' to {format_client_message(session=target_session)}",
                )

                handler = self._get_handler(target_session)
                if handler:
                    task = asyncio.ensure_future(
                        handler.mqtt_publish(
                            broadcast["topic"],
                            broadcast["data"],
                            qos,
                            retain=False,
                        ),
                    )
                    running_tasks.append(task)

    async def _retain_broadcast_message(self, broadcast: dict[str, Any], qos: int, target_session: Session) -> None:
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                f"retaining application message from {format_client_message(session=broadcast['session'])}"
                f" on topic '{broadcast['topic']}' to client '{format_client_message(session=target_session)}'",
            )

        retained_message = RetainedApplicationMessage(broadcast["session"], broadcast["topic"], broadcast["data"], qos)
        await target_session.retained_messages.put(retained_message)

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"target_session.retained_messages={target_session.retained_messages.qsize()}")

    async def _shutdown_broadcast_loop(self) -> None:
        if self._broadcast_task and not self._broadcast_shutdown_waiter.done():
            self._broadcast_shutdown_waiter.set_result(True)
            try:
                await asyncio.wait_for(self._broadcast_task, timeout=30)
            except TimeoutError as e:
                self.logger.warning(f"Failed to cleanly shutdown broadcast loop: {e}")

        if not self._broadcast_queue.empty():
            self.logger.warning(f"{self._broadcast_queue.qsize()} messages not broadcasted")

        self._broadcast_shutdown_waiter = asyncio.Future()

    async def _broadcast_message(
        self,
        session: Session | None,
        topic: str | None,
        data: bytes | bytearray | None,
        force_qos: int | None = None,
    ) -> None:
        broadcast: _BROADCAST = {"session": session, "topic": topic, "data": data}
        if force_qos is not None:
            broadcast["qos"] = force_qos
        await self._broadcast_queue.put(broadcast)

    async def _publish_session_retained_messages(self, session: Session) -> None:
        self.logger.debug(
            f"Publishing {session.retained_messages.qsize()}"
            f" messages retained for session {format_client_message(session=session)}",
        )
        publish_tasks = []
        handler = self._get_handler(session)
        if handler:
            while not session.retained_messages.empty():
                retained = await session.retained_messages.get()
                publish_tasks.append(
                    asyncio.ensure_future(
                        handler.mqtt_publish(retained.topic, retained.data, retained.qos, retain=True),
                    ),
                )
        if publish_tasks:
            await asyncio.wait(publish_tasks)

    async def _publish_retained_messages_for_subscription(self, subscription: tuple[str, int], session: Session) -> None:
        self.logger.debug(
            f"Begin broadcasting messages retained due to subscription on '{subscription[0]}'"
            f" from {format_client_message(session=session)}",
        )
        publish_tasks = []

        topic_filter, qos = subscription
        for topic, retained in self._retained_messages.items():
            self.logger.debug(f"matching : {topic} {topic_filter}")
            if self._matches(topic, topic_filter):
                self.logger.debug(f"{topic} and {topic_filter} match")
                handler = self._get_handler(session)
                if handler:
                    publish_tasks.append(
                        asyncio.Task(
                            handler.mqtt_publish(retained.topic, retained.data, min(qos, retained.qos or qos), retain=True),
                        ),
                    )
        if publish_tasks:
            await asyncio.wait(publish_tasks)
        self.logger.debug(
            f"End broadcasting messages retained due to subscription on '{subscription[0]}'"
            f" from {format_client_message(session=session)}",
        )

    def _matches(self, topic: str, a_filter: str) -> bool:
        if "#" not in a_filter and "+" not in a_filter:
            # if filter doesn't contain wildcard, return exact match
            return a_filter == topic
        # else use regex
        match_pattern = re.compile(re.escape(a_filter).replace("\\#", "?.*").replace("\\+", "[^/]*").lstrip("?"))
        return bool(match_pattern.fullmatch(topic))

    def _get_handler(self, session: Session) -> BrokerProtocolHandler | None:
        client_id = session.client_id
        if client_id:
            return self._sessions.get(client_id, (None, None))[1]
        return None

    @classmethod
    def _split_bindaddr_port(cls, port_str: str, default_port: int) -> tuple[str | None, int]:
        """Split an address:port pair into separate IP address and port. with IPv6 special-case handling.

        - Address can be specified using one of the following methods:
        - empty string      - all interfaces default port
        - 1883              - Port number only (listen all interfaces)
        - :1883             - Port number only (listen all interfaces)
        - 0.0.0.0:1883      - IPv4 address
        - [::]:1883         - IPv6 address
        """

        def _parse_port(port_str: str) -> int:
            port_str = port_str.removeprefix(":")

            if not port_str:
                return default_port

            return int(port_str)

        if port_str.startswith("["):  # IPv6 literal
            try:
                addr_end = port_str.index("]")
            except ValueError as e:
                msg = "Expecting '[' to be followed by ']'"
                raise ValueError(msg) from e

            return (port_str[0 : addr_end + 1], _parse_port(port_str[addr_end + 1 :]))

        if ":" in port_str:
            address, port_str = port_str.rsplit(":", 1)
            return (address or None, _parse_port(port_str))

        try:
            return (None, _parse_port(port_str))
        except ValueError:
            return (port_str, default_port)

    @property
    def subscriptions(self) -> dict[str, list[tuple[Session, int]]]:
        return self._subscriptions

    @property
    def retained_messages(self) -> dict[str, RetainedApplicationMessage]:
        return self._retained_messages

    @property
    def sessions(self) -> dict[str, tuple[Session, BrokerProtocolHandler]]:
        return self._sessions
