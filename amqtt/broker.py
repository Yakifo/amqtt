# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from typing import Optional
import logging
import ssl
import websockets
import asyncio
import re
from asyncio import CancelledError, futures
from collections import deque
from enum import Enum

from functools import partial
from transitions import Machine, MachineError
from amqtt.session import Session
from amqtt.mqtt.protocol.broker_handler import BrokerProtocolHandler
from amqtt.errors import AMQTTException, MQTTException
from amqtt.utils import format_client_message, gen_client_id
from amqtt.adapters import (
    StreamReaderAdapter,
    StreamWriterAdapter,
    ReaderAdapter,
    WriterAdapter,
    WebSocketsReader,
    WebSocketsWriter,
)
from .plugins.manager import PluginManager, BaseContext


_defaults = {
    "timeout-disconnect-delay": 2,
    "auth": {"allow-anonymous": True, "password-file": None},
}

EVENT_BROKER_PRE_START = "broker_pre_start"
EVENT_BROKER_POST_START = "broker_post_start"
EVENT_BROKER_PRE_SHUTDOWN = "broker_pre_shutdown"
EVENT_BROKER_POST_SHUTDOWN = "broker_post_shutdown"
EVENT_BROKER_CLIENT_CONNECTED = "broker_client_connected"
EVENT_BROKER_CLIENT_DISCONNECTED = "broker_client_disconnected"
EVENT_BROKER_CLIENT_SUBSCRIBED = "broker_client_subscribed"
EVENT_BROKER_CLIENT_UNSUBSCRIBED = "broker_client_unsubscribed"
EVENT_BROKER_MESSAGE_RECEIVED = "broker_message_received"


class Action(Enum):
    subscribe = "subscribe"
    publish = "publish"


class BrokerException(Exception):
    pass


class RetainedApplicationMessage:

    __slots__ = ("source_session", "topic", "data", "qos")

    def __init__(self, source_session, topic, data, qos=None):
        self.source_session = source_session
        self.topic = topic
        self.data = data
        self.qos = qos


class Server:
    def __init__(self, listener_name, server_instance, max_connections=-1):
        self.logger = logging.getLogger(__name__)
        self.instance = server_instance
        self.conn_count = 0
        self.listener_name = listener_name

        self.max_connections = max_connections
        if self.max_connections > 0:
            self.semaphore = asyncio.Semaphore(self.max_connections)
        else:
            self.semaphore = None

    async def acquire_connection(self):
        if self.semaphore:
            await self.semaphore.acquire()
        self.conn_count += 1
        if self.max_connections > 0:
            self.logger.info(
                "Listener '%s': %d/%d connections acquired"
                % (self.listener_name, self.conn_count, self.max_connections)
            )
        else:
            self.logger.info(
                "Listener '%s': %d connections acquired"
                % (self.listener_name, self.conn_count)
            )

    def release_connection(self) -> None:
        if self.semaphore:
            self.semaphore.release()
        self.conn_count -= 1
        if self.max_connections > 0:
            self.logger.info(
                "Listener '%s': %d/%d connections acquired"
                % (self.listener_name, self.conn_count, self.max_connections)
            )
        else:
            self.logger.info(
                "Listener '%s': %d connections acquired"
                % (self.listener_name, self.conn_count)
            )

    async def close_instance(self):
        if self.instance:
            self.instance.close()
            await self.instance.wait_closed()


class BrokerContext(BaseContext):
    """
    BrokerContext is used as the context passed to plugins interacting with the broker.
    It act as an adapter to broker services from plugins developed for HBMQTT broker
    """

    def __init__(self, broker: "Broker") -> None:
        super().__init__()
        self.config = None
        self._broker_instance = broker

    async def broadcast_message(self, topic, data, qos=None):
        await self._broker_instance.internal_message_broadcast(topic, data, qos)

    def retain_message(self, topic_name, data, qos=None):
        self._broker_instance.retain_message(None, topic_name, data, qos)

    @property
    def sessions(self):
        for session in self._broker_instance._sessions.values():
            yield session[0]

    @property
    def retained_messages(self):
        return self._broker_instance._retained_messages

    @property
    def subscriptions(self):
        return self._broker_instance._subscriptions


class Broker:
    """
    MQTT 3.1.1 compliant broker implementation

    :param config: Example Yaml config
    :param loop: asyncio loop to use. Defaults to ``asyncio.get_event_loop()``.
    :param plugin_namespace: Plugin namespace to use when loading plugin entry_points. Defaults to ``amqtt.broker.plugins``

    """

    states = [
        "new",
        "starting",
        "started",
        "not_started",
        "stopping",
        "stopped",
        "not_stopped",
        "stopped",
    ]

    def __init__(self, config=None, loop=None, plugin_namespace=None):
        self.logger = logging.getLogger(__name__)
        self.config = _defaults
        if config is not None:
            self.config.update(config)
        self._build_listeners_config(self.config)

        if loop is not None:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()

        self._servers = dict()
        self._init_states()
        self._sessions = dict()
        self._subscriptions = dict()
        self._retained_messages = dict()
        self._broadcast_queue = asyncio.Queue()

        self._broadcast_task = None
        self._broadcast_shutdown_waiter = futures.Future()

        # Init plugins manager
        context = BrokerContext(self)
        context.config = self.config
        if plugin_namespace:
            namespace = plugin_namespace
        else:
            namespace = "amqtt.broker.plugins"
        self.plugins_manager = PluginManager(namespace, context, self._loop)

    def _build_listeners_config(self, broker_config):
        self.listeners_config = dict()
        try:
            listeners_config = broker_config["listeners"]
            defaults = listeners_config["default"]
            for listener in listeners_config:
                config = dict(defaults)
                config.update(listeners_config[listener])
                self.listeners_config[listener] = config
        except KeyError as ke:
            raise BrokerException("Listener config not found invalid: %s" % ke)

    def _init_states(self) -> None:
        self.transitions = Machine(states=Broker.states, initial="new")
        self.transitions.add_transition(trigger="start", source="new", dest="starting")
        self.transitions.add_transition(
            trigger="starting_fail", source="starting", dest="not_started"
        )
        self.transitions.add_transition(
            trigger="starting_success", source="starting", dest="started"
        )
        self.transitions.add_transition(
            trigger="shutdown", source="started", dest="stopping"
        )
        self.transitions.add_transition(
            trigger="stopping_success", source="stopping", dest="stopped"
        )
        self.transitions.add_transition(
            trigger="stopping_failure", source="stopping", dest="not_stopped"
        )
        self.transitions.add_transition(
            trigger="start", source="stopped", dest="starting"
        )

    async def start(self) -> None:
        """
        Start the broker to serve with the given configuration

        Start method opens network sockets and will start listening for incoming connections.

        This method is a *coroutine*.
        """
        try:
            self._sessions = dict()
            self._subscriptions = dict()
            self._retained_messages = dict()
            self.transitions.start()
            self.logger.debug("Broker starting")
        except (MachineError, ValueError) as exc:
            # Backwards compat: MachineError is raised by transitions < 0.5.0.
            self.logger.warning(
                "[WARN-0001] Invalid method call at this moment: %s" % exc
            )
            raise BrokerException("Broker instance can't be started: %s" % exc)

        await self.plugins_manager.fire_event(EVENT_BROKER_PRE_START)
        try:
            # Start network listeners
            for listener_name in self.listeners_config:
                listener = self.listeners_config[listener_name]

                if "bind" not in listener:
                    self.logger.debug(
                        "Listener configuration '%s' is not bound" % listener_name
                    )
                    continue

                max_connections = listener.get("max_connections", -1)

                # SSL Context
                sc = None

                # accept string "on" / "off" or boolean
                ssl_active = listener.get("ssl", False)
                if isinstance(ssl_active, str):
                    ssl_active = ssl_active.upper() == "ON"

                if ssl_active:
                    try:
                        sc = ssl.create_default_context(
                            ssl.Purpose.CLIENT_AUTH,
                            cafile=listener.get("cafile"),
                            capath=listener.get("capath"),
                            cadata=listener.get("cadata"),
                        )
                        sc.load_cert_chain(listener["certfile"], listener["keyfile"])
                        sc.verify_mode = ssl.CERT_OPTIONAL
                    except KeyError as ke:
                        raise BrokerException(
                            "'certfile' or 'keyfile' configuration parameter missing: %s"
                            % ke
                        )
                    except FileNotFoundError as fnfe:
                        raise BrokerException(
                            "Can't read cert files '%s' or '%s' : %s"
                            % (listener["certfile"], listener["keyfile"], fnfe)
                        )

                address, s_port = listener["bind"].split(":")
                port = 0
                try:
                    port = int(s_port)
                except ValueError:
                    raise BrokerException(
                        "Invalid port value in bind value: %s" % listener["bind"]
                    )

                if listener["type"] == "tcp":
                    cb_partial = partial(
                        self.stream_connected, listener_name=listener_name
                    )
                    instance = await asyncio.start_server(
                        cb_partial,
                        address,
                        port,
                        reuse_address=True,
                        ssl=sc,
                    )
                    self._servers[listener_name] = Server(
                        listener_name, instance, max_connections
                    )
                elif listener["type"] == "ws":
                    cb_partial = partial(self.ws_connected, listener_name=listener_name)
                    instance = await websockets.serve(
                        cb_partial,
                        address,
                        port,
                        ssl=sc,
                        subprotocols=["mqtt"],
                    )
                    self._servers[listener_name] = Server(
                        listener_name, instance, max_connections
                    )

                self.logger.info(
                    "Listener '%s' bind to %s (max_connections=%d)"
                    % (listener_name, listener["bind"], max_connections)
                )

            self.transitions.starting_success()
            await self.plugins_manager.fire_event(EVENT_BROKER_POST_START)

            # Start broadcast loop
            self._broadcast_task = asyncio.ensure_future(self._broadcast_loop())

            self.logger.debug("Broker started")
        except Exception as e:
            self.logger.error("Broker startup failed: %s" % e)
            self.transitions.starting_fail()
            raise BrokerException("Broker instance can't be started: %s" % e)

    async def shutdown(self):
        """
        Stop broker instance.

        Closes all connected session, stop listening on network socket and free resources.
        """
        try:
            self._sessions = dict()
            self._subscriptions = dict()
            self._retained_messages = dict()
            self.transitions.shutdown()
        except (MachineError, ValueError) as exc:
            # Backwards compat: MachineError is raised by transitions < 0.5.0.
            self.logger.debug("Invalid method call at this moment: %s" % exc)
            raise BrokerException("Broker instance can't be stopped: %s" % exc)

        # Fire broker_shutdown event to plugins
        await self.plugins_manager.fire_event(EVENT_BROKER_PRE_SHUTDOWN)

        await self._shutdown_broadcast_loop()

        for listener_name in self._servers:
            server = self._servers[listener_name]
            await server.close_instance()
        self.logger.debug("Broker closing")
        self.logger.info("Broker closed")
        await self.plugins_manager.fire_event(EVENT_BROKER_POST_SHUTDOWN)
        self.transitions.stopping_success()

    async def internal_message_broadcast(self, topic, data, qos=None):
        return await self._broadcast_message(None, topic, data)

    async def ws_connected(self, websocket, uri, listener_name):
        await self.client_connected(
            listener_name, WebSocketsReader(websocket), WebSocketsWriter(websocket)
        )

    async def stream_connected(self, reader, writer, listener_name):
        await self.client_connected(
            listener_name, StreamReaderAdapter(reader), StreamWriterAdapter(writer)
        )

    async def client_connected(
        self, listener_name, reader: ReaderAdapter, writer: WriterAdapter
    ):
        # Wait for connection available on listener
        server = self._servers.get(listener_name, None)
        if not server:
            raise BrokerException("Invalid listener name '%s'" % listener_name)
        await server.acquire_connection()

        remote_address, remote_port = writer.get_peer_info()
        self.logger.info(
            "Connection from %s:%d on listener '%s'"
            % (remote_address, remote_port, listener_name)
        )

        # Wait for first packet and expect a CONNECT
        try:
            handler, client_session = await BrokerProtocolHandler.init_from_connect(
                reader, writer, self.plugins_manager
            )
        except AMQTTException as exc:
            self.logger.warning(
                "[MQTT-3.1.0-1] %s: Can't read first packet an CONNECT: %s"
                % (format_client_message(address=remote_address, port=remote_port), exc)
            )
            # await writer.close()
            self.logger.debug("Connection closed")
            return
        except MQTTException as me:
            self.logger.error(
                "Invalid connection from %s : %s"
                % (format_client_message(address=remote_address, port=remote_port), me)
            )
            await writer.close()
            self.logger.debug("Connection closed")
            return

        if client_session.clean_session:
            # Delete existing session and create a new one
            if client_session.client_id is not None and client_session.client_id != "":
                self.delete_session(client_session.client_id)
            else:
                client_session.client_id = gen_client_id()
            client_session.parent = 0
        else:
            # Get session from cache
            if client_session.client_id in self._sessions:
                self.logger.debug(
                    "Found old session %s"
                    % repr(self._sessions[client_session.client_id])
                )
                (client_session, h) = self._sessions[client_session.client_id]
                client_session.parent = 1
            else:
                client_session.parent = 0
        if client_session.keep_alive > 0:
            client_session.keep_alive += self.config["timeout-disconnect-delay"]
        self.logger.debug("Keep-alive timeout=%d" % client_session.keep_alive)

        authenticated = await self.authenticate(
            client_session, self.listeners_config[listener_name]
        )
        if not authenticated:
            await writer.close()
            server.release_connection()  # Delete client from connections list
            return

        while True:
            try:
                client_session.transitions.connect()
                break
            except (MachineError, ValueError):
                # Backwards compat: MachineError is raised by transitions < 0.5.0.
                if client_session.transitions.is_connected():
                    self.logger.warning(
                        "Client %s is already connected, performing take-over.",
                        client_session.client_id,
                    )
                    old_session = self._sessions[client_session.client_id]
                    await old_session[1].handle_connection_closed()
                    await old_session[1].stop()
                    break
                else:
                    self.logger.warning(
                        "Client %s is reconnecting too quickly, make it wait"
                        % client_session.client_id
                    )
                    # Wait a bit may be client is reconnecting too fast
                    await asyncio.sleep(1)

        handler.attach(client_session, reader, writer)
        self._sessions[client_session.client_id] = (client_session, handler)

        await handler.mqtt_connack_authorize(authenticated)

        await self.plugins_manager.fire_event(
            EVENT_BROKER_CLIENT_CONNECTED, client_id=client_session.client_id
        )

        self.logger.debug("%s Start messages handling" % client_session.client_id)
        await handler.start()
        self.logger.debug(
            "Retained messages queue size: %d"
            % client_session.retained_messages.qsize()
        )
        await self.publish_session_retained_messages(client_session)

        # Init and start loop for handling client messages (publish, subscribe/unsubscribe, disconnect)
        disconnect_waiter = asyncio.ensure_future(handler.wait_disconnect())
        subscribe_waiter = asyncio.ensure_future(
            handler.get_next_pending_subscription()
        )
        unsubscribe_waiter = asyncio.ensure_future(
            handler.get_next_pending_unsubscription()
        )
        wait_deliver = asyncio.ensure_future(handler.mqtt_deliver_next_message())
        connected = True
        while connected:
            try:
                done, pending = await asyncio.wait(
                    [
                        disconnect_waiter,
                        subscribe_waiter,
                        unsubscribe_waiter,
                        wait_deliver,
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if disconnect_waiter in done:
                    result = disconnect_waiter.result()
                    self.logger.debug(
                        "%s Result from wait_diconnect: %s"
                        % (client_session.client_id, result)
                    )
                    if result is None:
                        self.logger.debug("Will flag: %s" % client_session.will_flag)
                        # Connection closed anormally, send will message
                        if client_session.will_flag:
                            self.logger.debug(
                                "Client %s disconnected abnormally, sending will message"
                                % format_client_message(client_session)
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
                    self.logger.debug(
                        "%s Disconnecting session" % client_session.client_id
                    )
                    await self._stop_handler(handler)
                    client_session.transitions.disconnect()
                    await self.plugins_manager.fire_event(
                        EVENT_BROKER_CLIENT_DISCONNECTED,
                        client_id=client_session.client_id,
                    )
                    connected = False
                if unsubscribe_waiter in done:
                    self.logger.debug(
                        "%s handling unsubscription" % client_session.client_id
                    )
                    unsubscription = unsubscribe_waiter.result()
                    for topic in unsubscription["topics"]:
                        self._del_subscription(topic, client_session)
                        await self.plugins_manager.fire_event(
                            EVENT_BROKER_CLIENT_UNSUBSCRIBED,
                            client_id=client_session.client_id,
                            topic=topic,
                        )
                    await handler.mqtt_acknowledge_unsubscription(
                        unsubscription["packet_id"]
                    )
                    unsubscribe_waiter = asyncio.Task(
                        handler.get_next_pending_unsubscription()
                    )
                if subscribe_waiter in done:
                    self.logger.debug(
                        "%s handling subscription" % client_session.client_id
                    )
                    subscriptions = subscribe_waiter.result()
                    return_codes = []
                    for subscription in subscriptions["topics"]:
                        result = await self.add_subscription(
                            subscription, client_session
                        )
                        return_codes.append(result)
                    await handler.mqtt_acknowledge_subscription(
                        subscriptions["packet_id"], return_codes
                    )
                    for index, subscription in enumerate(subscriptions["topics"]):
                        if return_codes[index] != 0x80:
                            await self.plugins_manager.fire_event(
                                EVENT_BROKER_CLIENT_SUBSCRIBED,
                                client_id=client_session.client_id,
                                topic=subscription[0],
                                qos=subscription[1],
                            )
                            await self.publish_retained_messages_for_subscription(
                                subscription, client_session
                            )
                    subscribe_waiter = asyncio.Task(
                        handler.get_next_pending_subscription()
                    )
                    self.logger.debug(repr(self._subscriptions))
                if wait_deliver in done:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(
                            "%s handling message delivery" % client_session.client_id
                        )
                    app_message = wait_deliver.result()
                    if not app_message.topic:
                        self.logger.warning(
                            "[MQTT-4.7.3-1] - %s invalid TOPIC sent in PUBLISH message, closing connection"
                            % client_session.client_id
                        )
                        break
                    if "#" in app_message.topic or "+" in app_message.topic:
                        self.logger.warning(
                            "[MQTT-3.3.2-2] - %s invalid TOPIC sent in PUBLISH message, closing connection"
                            % client_session.client_id
                        )
                        break

                    # See if the user is allowed to publish to this topic.
                    permitted = await self.topic_filtering(
                        client_session, topic=app_message.topic, action=Action.publish
                    )
                    if not permitted:
                        self.logger.info(
                            "%s forbidden TOPIC %s sent in PUBLISH message.",
                            client_session.client_id,
                            app_message.topic,
                        )
                    else:
                        await self.plugins_manager.fire_event(
                            EVENT_BROKER_MESSAGE_RECEIVED,
                            client_id=client_session.client_id,
                            message=app_message,
                        )
                        await self._broadcast_message(
                            client_session, app_message.topic, app_message.data
                        )
                        if app_message.publish_packet.retain_flag:
                            self.retain_message(
                                client_session,
                                app_message.topic,
                                app_message.data,
                                app_message.qos,
                            )
                    wait_deliver = asyncio.Task(handler.mqtt_deliver_next_message())
            except asyncio.CancelledError:
                self.logger.debug("Client loop cancelled")
                break
        disconnect_waiter.cancel()
        subscribe_waiter.cancel()
        unsubscribe_waiter.cancel()
        wait_deliver.cancel()

        self.logger.debug("%s Client disconnected" % client_session.client_id)
        server.release_connection()

    def _init_handler(self, session, reader, writer):
        """
        Create a BrokerProtocolHandler and attach to a session
        :return:
        """
        handler = BrokerProtocolHandler(self.plugins_manager, self._loop)
        handler.attach(session, reader, writer)
        return handler

    async def _stop_handler(self, handler):
        """
        Stop a running handler and detach if from the session
        :param handler:
        :return:
        """
        try:
            await handler.stop()
        except Exception as e:
            self.logger.error(e)

    async def authenticate(self, session: Session, listener):
        """
        This method call the authenticate method on registered plugins to test user authentication.
        User is considered authenticated if all plugins called returns True.
        Plugins authenticate() method are supposed to return :
         - True if user is authentication succeed
         - False if user authentication fails
         - None if authentication can't be achieved (then plugin result is then ignored)
        :param session:
        :param listener:
        :return:
        """
        auth_plugins = None
        auth_config = self.config.get("auth", None)
        if auth_config:
            auth_plugins = auth_config.get("plugins", None)
        returns = await self.plugins_manager.map_plugin_coro(
            "authenticate", session=session, filter_plugins=auth_plugins
        )
        auth_result = True
        if returns:
            for plugin in returns:
                res = returns[plugin]
                if res is False:
                    auth_result = False
                    self.logger.debug(
                        "Authentication failed due to '%s' plugin result: %s"
                        % (plugin.name, res)
                    )
                else:
                    self.logger.debug("'%s' plugin result: %s" % (plugin.name, res))
        # If all plugins returned True, authentication is success
        return auth_result

    async def topic_filtering(self, session: Session, topic, action: Action):
        """
        This method call the topic_filtering method on registered plugins to check that the subscription is allowed.
        User is considered allowed if all plugins called return True.
        Plugins topic_filtering() method are supposed to return :
         - True if MQTT client can be subscribed to the topic
         - False if MQTT client is not allowed to subscribe to the topic
         - None if topic filtering can't be achieved (then plugin result is then ignored)
        :param session:
        :param listener:
        :param topic: Topic in which the client wants to subscribe / publish
        :param action: What is being done with the topic?  subscribe or publish
        :return:
        """
        topic_result = True
        topic_plugins = None
        topic_config = self.config.get("topic-check", None)
        # if enabled is not specified, all plugins will be used for topic filtering (backward compatibility)
        if topic_config and "enabled" in topic_config:
            if topic_config.get("enabled", False):
                topic_plugins = topic_config.get("plugins", None)
            else:
                return topic_result

        returns = await self.plugins_manager.map_plugin_coro(
            "topic_filtering",
            session=session,
            topic=topic,
            action=action,
            filter_plugins=topic_plugins,
        )
        if returns:
            for plugin in returns:
                res = returns[plugin]
                if res is False:
                    topic_result = False
                    self.logger.debug(
                        "Topic filtering failed due to '%s' plugin result: %s"
                        % (plugin.name, res)
                    )
                else:
                    self.logger.debug("'%s' plugin result: %s" % (plugin.name, res))
        # If all plugins returned True, authentication is success
        return topic_result

    def retain_message(
        self,
        source_session: Session,
        topic_name: str,
        data: bytearray,
        qos: Optional[int] = None,
    ) -> None:
        if data is not None and data != b"":
            # If retained flag set, store the message for further subscriptions
            self.logger.debug("Retaining message on topic %s" % topic_name)
            retained_message = RetainedApplicationMessage(
                source_session, topic_name, data, qos
            )
            self._retained_messages[topic_name] = retained_message
        else:
            # [MQTT-3.3.1-10]
            if topic_name in self._retained_messages:
                self.logger.debug("Clear retained messages for topic '%s'" % topic_name)
                del self._retained_messages[topic_name]

    async def add_subscription(self, subscription, session):
        try:
            a_filter = subscription[0]
            if "#" in a_filter and not a_filter.endswith("#"):
                # [MQTT-4.7.1-2] Wildcard character '#' is only allowed as last character in filter
                return 0x80
            if a_filter != "+":
                if "+" in a_filter:
                    if "/+" not in a_filter and "+/" not in a_filter:
                        # [MQTT-4.7.1-3] + wildcard character must occupy entire level
                        return 0x80
            # Check if the client is authorised to connect to the topic
            permitted = await self.topic_filtering(
                session, topic=a_filter, action=Action.subscribe
            )
            if not permitted:
                return 0x80
            qos = subscription[1]
            if "max-qos" in self.config and qos > self.config["max-qos"]:
                qos = self.config["max-qos"]
            if a_filter not in self._subscriptions:
                self._subscriptions[a_filter] = []
            already_subscribed = next(
                (
                    s
                    for (s, qos) in self._subscriptions[a_filter]
                    if s.client_id == session.client_id
                ),
                None,
            )
            if not already_subscribed:
                self._subscriptions[a_filter].append((session, qos))
            else:
                self.logger.debug(
                    "Client %s has already subscribed to %s"
                    % (format_client_message(session=session), a_filter)
                )
            return qos
        except KeyError:
            return 0x80

    def _del_subscription(self, a_filter: str, session: Session) -> int:
        """
        Delete a session subscription on a given topic
        :param a_filter:
        :param session:
        :return:
        """
        deleted = 0
        try:
            subscriptions = self._subscriptions[a_filter]
            for index, (sub_session, qos) in enumerate(subscriptions):
                if sub_session.client_id == session.client_id:
                    self.logger.debug(
                        "Removing subscription on topic '%s' for client %s"
                        % (a_filter, format_client_message(session=session))
                    )
                    subscriptions.pop(index)
                    deleted += 1
                    break
        except KeyError:
            # Unsubscribe topic not found in current subscribed topics
            pass
        finally:
            return deleted

    def _del_all_subscriptions(self, session: Session) -> None:
        """
        Delete all topic subscriptions for a given session
        :param session:
        :return:
        """
        filter_queue = deque()
        for topic in self._subscriptions:
            if self._del_subscription(topic, session):
                filter_queue.append(topic)
        for topic in filter_queue:
            if not self._subscriptions[topic]:
                del self._subscriptions[topic]

    def matches(self, topic, a_filter):
        if "#" not in a_filter and "+" not in a_filter:
            # if filter doesn't contain wildcard, return exact match
            return a_filter == topic
        else:
            # else use regex
            match_pattern = re.compile(
                re.escape(a_filter)
                .replace("\\#", "?.*")
                .replace("\\+", "[^/]*")
                .lstrip("?")
            )
            return match_pattern.fullmatch(topic)

    async def _broadcast_loop(self):
        running_tasks = deque()
        try:
            while True:
                while running_tasks and running_tasks[0].done():
                    task = running_tasks.popleft()
                    try:
                        task.result()  # make asyncio happy and collect results
                    except CancelledError:
                        self.logger.info("Task has been cancelled: %s", task)
                    except Exception:
                        self.logger.exception(
                            "Task failed and will be skipped: %s", task
                        )

                run_broadcast_task = asyncio.Task(self._run_broadcast(running_tasks))

                completed, _ = await asyncio.wait(
                    [run_broadcast_task, self._broadcast_shutdown_waiter],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Shutdown has been triggered by the broker
                # So stop the loop execution
                if self._broadcast_shutdown_waiter in completed:
                    run_broadcast_task.cancel()
                    break

        except BaseException:
            self.logger.exception("Broadcast loop stopped by exception")
            raise
        finally:
            # Wait until current broadcasting tasks end
            if running_tasks:
                await asyncio.wait(running_tasks)

    async def _run_broadcast(self, running_tasks: deque):
        broadcast = await self._broadcast_queue.get()

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("broadcasting %r", broadcast)

        for k_filter in self._subscriptions:
            if broadcast["topic"].startswith("$") and (
                k_filter.startswith("+") or k_filter.startswith("#")
            ):
                self.logger.debug(
                    "[MQTT-4.7.2-1] - ignoring broadcasting $ topic to subscriptions starting with + or #"
                )
                continue

            # Skip all subscriptions which do not match the topic
            if not self.matches(broadcast["topic"], k_filter):
                continue

            subscriptions = self._subscriptions[k_filter]
            for (target_session, qos) in subscriptions:
                qos = broadcast.get("qos", qos)

                # Retain all messages which cannot be broadcasted
                # due to the session not being connected
                if target_session.transitions.state != "connected":
                    await self._retain_broadcast_message(broadcast, qos, target_session)
                    continue

                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(
                        "broadcasting application message from %s on topic '%s' to %s"
                        % (
                            format_client_message(session=broadcast["session"]),
                            broadcast["topic"],
                            format_client_message(session=target_session),
                        )
                    )

                handler = self._get_handler(target_session)
                task = asyncio.ensure_future(
                    handler.mqtt_publish(
                        broadcast["topic"],
                        broadcast["data"],
                        qos,
                        retain=False,
                    ),
                )
                running_tasks.append(task)

    async def _retain_broadcast_message(self, broadcast, qos, target_session):
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "retaining application message from %s on topic '%s' to client '%s'",
                format_client_message(session=broadcast["session"]),
                broadcast["topic"],
                format_client_message(session=target_session),
            )

        retained_message = RetainedApplicationMessage(
            broadcast["session"],
            broadcast["topic"],
            broadcast["data"],
            qos,
        )
        await target_session.retained_messages.put(retained_message)

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "target_session.retained_messages=%s",
                target_session.retained_messages.qsize(),
            )

    async def _shutdown_broadcast_loop(self):
        if self._broadcast_task:
            self._broadcast_shutdown_waiter.set_result(True)
            try:
                await asyncio.wait_for(self._broadcast_task, timeout=30)
            except BaseException as e:
                self.logger.warning("Failed to cleanly shutdown broadcast loop: %r", e)

        if self._broadcast_queue.qsize() > 0:
            self.logger.warning(
                "%d messages not broadcasted", self._broadcast_queue.qsize()
            )

    async def _broadcast_message(self, session, topic, data, force_qos=None):
        broadcast = {"session": session, "topic": topic, "data": data}
        if force_qos:
            broadcast["qos"] = force_qos
        await self._broadcast_queue.put(broadcast)

    async def publish_session_retained_messages(self, session):
        self.logger.debug(
            "Publishing %d messages retained for session %s"
            % (
                session.retained_messages.qsize(),
                format_client_message(session=session),
            )
        )
        publish_tasks = []
        handler = self._get_handler(session)
        while not session.retained_messages.empty():
            retained = await session.retained_messages.get()
            publish_tasks.append(
                asyncio.ensure_future(
                    handler.mqtt_publish(
                        retained.topic, retained.data, retained.qos, True
                    ),
                )
            )
        if publish_tasks:
            await asyncio.wait(publish_tasks)

    async def publish_retained_messages_for_subscription(self, subscription, session):
        self.logger.debug(
            "Begin broadcasting messages retained due to subscription on '%s' from %s"
            % (subscription[0], format_client_message(session=session))
        )
        publish_tasks = []
        handler = self._get_handler(session)
        for d_topic in self._retained_messages:
            self.logger.debug("matching : %s %s" % (d_topic, subscription[0]))
            if self.matches(d_topic, subscription[0]):
                self.logger.debug("%s and %s match" % (d_topic, subscription[0]))
                retained = self._retained_messages[d_topic]
                publish_tasks.append(
                    asyncio.Task(
                        handler.mqtt_publish(
                            retained.topic, retained.data, subscription[1], True
                        ),
                    )
                )
        if publish_tasks:
            await asyncio.wait(publish_tasks)
        self.logger.debug(
            "End broadcasting messages retained due to subscription on '%s' from %s"
            % (subscription[0], format_client_message(session=session))
        )

    def delete_session(self, client_id: str) -> None:
        """
        Delete an existing session data, for example due to clean session set in CONNECT
        :param client_id:
        :return:
        """
        try:
            session = self._sessions[client_id][0]
        except KeyError:
            session = None
        if session is None:
            self.logger.debug("Delete session : session %s doesn't exist" % client_id)
            return

        # Delete subscriptions
        self.logger.debug("deleting session %s subscriptions" % repr(session))
        self._del_all_subscriptions(session)

        self.logger.debug(
            "deleting existing session %s" % repr(self._sessions[client_id])
        )
        del self._sessions[client_id]

    def _get_handler(self, session):
        client_id = session.client_id
        if client_id:
            try:
                return self._sessions[client_id][1]
            except KeyError:
                pass
        return None
