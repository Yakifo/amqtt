# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

import asyncio
import logging
import ssl
import copy
from urllib.parse import urlparse, urlunparse
from functools import wraps

from amqtt.session import Session
from amqtt.mqtt.connack import CONNECTION_ACCEPTED
from amqtt.mqtt.protocol.client_handler import ClientProtocolHandler
from amqtt.adapters import (
    StreamReaderAdapter,
    StreamWriterAdapter,
    WebSocketsReader,
    WebSocketsWriter,
)
from amqtt.plugins.manager import PluginManager, BaseContext
from amqtt.mqtt.protocol.handler import ProtocolHandlerException
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
import websockets
from websockets import InvalidURI
from websockets import InvalidHandshake
from collections import deque


_defaults = {
    "keep_alive": 10,
    "ping_delay": 1,
    "default_qos": 0,
    "default_retain": False,
    "auto_reconnect": True,
    "reconnect_max_interval": 10,
    "reconnect_retries": 2,
}


class ClientException(Exception):
    pass


class ConnectException(ClientException):
    pass


class ClientContext(BaseContext):
    """
    ClientContext is used as the context passed to plugins interacting with the client.
    It act as an adapter to client services from plugins
    """

    def __init__(self):
        super().__init__()
        self.config = None


base_logger = logging.getLogger(__name__)


def mqtt_connected(func):
    """
    MQTTClient coroutines decorator which will wait until connection before calling the decorated method.
    :param func: coroutine to be called once connected
    :return: coroutine result
    """
    wraps(func)

    async def wrapper(self, *args, **kwargs):
        if not self._connected_state.is_set():
            base_logger.warning("Client not connected, waiting for it")
            _, pending = await asyncio.wait(
                [self._connected_state.wait(), self._no_more_connections.wait()],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            if self._no_more_connections.is_set():
                raise ClientException("Will not reconnect")
        return await func(self, *args, **kwargs)

    return wrapper


class MQTTClient:
    """
    MQTT client implementation.

    MQTTClient instances provides API for connecting to a broker and send/receive messages using the MQTT protocol.

    :param client_id: MQTT client ID to use when connecting to the broker. If none, it will generated randomly by :func:`amqtt.utils.gen_client_id`
    :param config: Client configuration
    :param loop: asynio loop to use
    :return: class instance
    """

    def __init__(self, client_id=None, config=None, loop=None):
        self.logger = logging.getLogger(__name__)
        self.config = copy.deepcopy(_defaults)
        if config is not None:
            self.config.update(config)
        if client_id is not None:
            self.client_id = client_id
        else:
            from amqtt.utils import gen_client_id

            self.client_id = gen_client_id()
            self.logger.debug("Using generated client ID : %s" % self.client_id)

        if loop is not None:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()
        self.session = None
        self._handler = None
        self._disconnect_task = None
        self._connected_state = asyncio.Event(loop=self._loop)
        self._no_more_connections = asyncio.Event(loop=self._loop)
        self.extra_headers = {}

        # Init plugins manager
        context = ClientContext()
        context.config = self.config
        self.plugins_manager = PluginManager(
            "amqtt.client.plugins", context, loop=self._loop
        )
        self.client_tasks = deque()

    async def connect(
        self,
        uri=None,
        cleansession=None,
        cafile=None,
        capath=None,
        cadata=None,
        extra_headers=None,
    ):
        """
        Connect to a remote broker.

        At first, a network connection is established with the server using the given protocol (``mqtt``, ``mqtts``, ``ws`` or ``wss``). Once the socket is connected, a `CONNECT <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718028>`_ message is sent with the requested informations.

        This method is a *coroutine*.

        :param uri: Broker URI connection, conforming to `MQTT URI scheme <https://github.com/mqtt/mqtt.github.io/wiki/URI-Scheme>`_. Uses ``uri`` config attribute by default.
        :param cleansession: MQTT CONNECT clean session flag
        :param cafile: server certificate authority file (optional, used for secured connection)
        :param capath: server certificate authority path (optional, used for secured connection)
        :param cadata: server certificate authority data (optional, used for secured connection)
        :param extra_headers: a dictionary with additional http headers that should be sent on the initial connection (optional, used only with websocket connections)
        :return: `CONNACK <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718033>`_ return code
        :raise: :class:`amqtt.client.ConnectException` if connection fails
        """

        if extra_headers is None:
            extra_headers = {}

        self.session = self._initsession(uri, cleansession, cafile, capath, cadata)
        self.extra_headers = extra_headers
        self.logger.debug("Connect to: %s" % uri)

        try:
            return await self._do_connect()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.warning("Connection failed: %r" % e)
            auto_reconnect = self.config.get("auto_reconnect", False)
            if not auto_reconnect:
                raise
            else:
                return await self.reconnect()

    async def disconnect(self):
        """
        Disconnect from the connected broker.

        This method sends a `DISCONNECT <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718090>`_ message and closes the network socket.

        This method is a *coroutine*.
        """
        await self.cancel_tasks()
        if self.session.transitions.is_connected():
            if not self._disconnect_task.done():
                self._disconnect_task.cancel()
            await self._handler.mqtt_disconnect()
            self._connected_state.clear()
            await self._handler.stop()
            self.session.transitions.disconnect()
        else:
            self.logger.warning(
                "Client session is not currently connected, ignoring call"
            )

    async def cancel_tasks(self):
        """
        Before disconnection need to cancel all pending tasks
        :return:
        """
        try:
            while self.client_tasks:
                task = self.client_tasks.pop()
                task.cancel()
        except IndexError:
            pass

    async def reconnect(self, cleansession=None):
        """
        Reconnect a previously connected broker.

        Reconnection tries to establish a network connection and send a `CONNECT <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718028>`_ message.
        Retries interval and attempts can be controlled with the ``reconnect_max_interval`` and ``reconnect_retries`` configuration parameters.

        This method is a *coroutine*.

        :param cleansession: clean session flag used in MQTT CONNECT messages sent for reconnections.
        :return: `CONNACK <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718033>`_ return code
        :raise: :class:`amqtt.client.ConnectException` if re-connection fails after max retries.
        """

        if self.session.transitions.is_connected():
            self.logger.warning("Client already connected")
            return CONNECTION_ACCEPTED

        if cleansession:
            self.session.clean_session = cleansession
        self.logger.debug("Reconnecting with session parameters: %s" % self.session)
        reconnect_max_interval = self.config.get("reconnect_max_interval", 10)
        reconnect_retries = self.config.get("reconnect_retries", 5)
        nb_attempt = 1
        await asyncio.sleep(1, loop=self._loop)
        while True:
            try:
                self.logger.debug("Reconnect attempt %d ..." % nb_attempt)
                return await self._do_connect()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.warning("Reconnection attempt failed: %r" % e)
                if reconnect_retries >= 0 and nb_attempt > reconnect_retries:
                    self.logger.error(
                        "Maximum number of connection attempts reached. Reconnection aborted"
                    )
                    raise ConnectException("Too many connection attempts failed") from e
                exp = 2 ** nb_attempt
                delay = exp if exp < reconnect_max_interval else reconnect_max_interval
                self.logger.debug("Waiting %d second before next attempt" % delay)
                await asyncio.sleep(delay, loop=self._loop)
                nb_attempt += 1

    async def _do_connect(self):
        return_code = await self._connect_coro()
        self._disconnect_task = asyncio.ensure_future(
            self.handle_connection_close(), loop=self._loop
        )
        return return_code

    @mqtt_connected
    async def ping(self):
        """
        Ping the broker.

        Send a MQTT `PINGREQ <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718081>`_ message for response.

        This method is a *coroutine*.
        """

        if self.session.transitions.is_connected():
            await self._handler.mqtt_ping()
        else:
            self.logger.warning(
                "MQTT PING request incompatible with current session state '%s'"
                % self.session.transitions.state
            )

    @mqtt_connected
    async def publish(self, topic, message, qos=None, retain=None, ack_timeout=None):
        """
        Publish a message to the broker.

        Send a MQTT `PUBLISH <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718037>`_ message and wait for acknowledgment depending on Quality Of Service

        This method is a *coroutine*.

        :param topic: topic name to which message data is published
        :param message: payload message (as bytes) to send.
        :param qos: requested publish quality of service : QOS_0, QOS_1 or QOS_2. Defaults to ``default_qos`` config parameter or QOS_0.
        :param retain: retain flag. Defaults to ``default_retain`` config parameter or False.
        """

        def get_retain_and_qos():
            if qos:
                assert qos in (QOS_0, QOS_1, QOS_2)
                _qos = qos
            else:
                _qos = self.config["default_qos"]
                try:
                    _qos = self.config["topics"][topic]["qos"]
                except KeyError:
                    pass
            if retain:
                _retain = retain
            else:
                _retain = self.config["default_retain"]
                try:
                    _retain = self.config["topics"][topic]["retain"]
                except KeyError:
                    pass
            return _qos, _retain

        (app_qos, app_retain) = get_retain_and_qos()
        return await self._handler.mqtt_publish(
            topic, message, app_qos, app_retain, ack_timeout
        )

    @mqtt_connected
    async def subscribe(self, topics):
        """
        Subscribe to some topics.

        Send a MQTT `SUBSCRIBE <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718063>`_ message and wait for broker acknowledgment.

        This method is a *coroutine*.

        :param topics: array of topics pattern to subscribe with associated QoS.
        :return: `SUBACK <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718068>`_ message return code.

        Example of ``topics`` argument expected structure:
        ::

            [
                ('$SYS/broker/uptime', QOS_1),
                ('$SYS/broker/load/#', QOS_2),
            ]
        """
        return await self._handler.mqtt_subscribe(topics, self.session.next_packet_id)

    @mqtt_connected
    async def unsubscribe(self, topics):
        """
        Unsubscribe from some topics.

        Send a MQTT `UNSUBSCRIBE <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718072>`_ message and wait for broker `UNSUBACK <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718077>`_ message.

        This method is a *coroutine*.

        :param topics: array of topics to unsubscribe from.

        Example of ``topics`` argument expected structure:
        ::

            ['$SYS/broker/uptime', '$SYS/broker/load/#']
        """
        await self._handler.mqtt_unsubscribe(topics, self.session.next_packet_id)

    async def deliver_message(self, timeout=None):
        """
        Deliver next received message.

        Deliver next message received from the broker. If no message is available, this methods waits until next message arrives or ``timeout`` occurs.

        This method is a *coroutine*.

        :param timeout: maximum number of seconds to wait before returning. If timeout is not specified or None, there is no limit to the wait time until next message arrives.
        :return: instance of :class:`amqtt.session.ApplicationMessage` containing received message information flow.
        :raises: :class:`asyncio.TimeoutError` if timeout occurs before a message is delivered
        """
        deliver_task = asyncio.ensure_future(
            self._handler.mqtt_deliver_next_message(), loop=self._loop
        )
        self.client_tasks.append(deliver_task)
        self.logger.debug("Waiting message delivery")
        done, pending = await asyncio.wait(
            [deliver_task],
            loop=self._loop,
            return_when=asyncio.FIRST_EXCEPTION,
            timeout=timeout,
        )
        if self.client_tasks:
            self.client_tasks.pop()
        if deliver_task in done:
            if deliver_task.exception() is not None:
                # deliver_task raised an exception, pass it on to our caller
                raise deliver_task.exception()
            return deliver_task.result()
        else:
            # timeout occured before message received
            deliver_task.cancel()
            raise asyncio.TimeoutError

    async def _connect_coro(self):
        kwargs = dict()

        # Decode URI attributes
        uri_attributes = urlparse(self.session.broker_uri)
        scheme = uri_attributes.scheme
        secure = True if scheme in ("mqtts", "wss") else False
        self.session.username = (
            self.session.username if self.session.username else uri_attributes.username
        )
        self.session.password = (
            self.session.password if self.session.password else uri_attributes.password
        )
        self.session.remote_address = uri_attributes.hostname
        self.session.remote_port = uri_attributes.port
        if scheme in ("mqtt", "mqtts") and not self.session.remote_port:
            self.session.remote_port = 8883 if scheme == "mqtts" else 1883
        if scheme in ("ws", "wss") and not self.session.remote_port:
            self.session.remote_port = 443 if scheme == "wss" else 80
        if scheme in ("ws", "wss"):
            # Rewrite URI to conform to https://tools.ietf.org/html/rfc6455#section-3
            uri = (
                scheme,
                self.session.remote_address + ":" + str(self.session.remote_port),
                uri_attributes[2],
                uri_attributes[3],
                uri_attributes[4],
                uri_attributes[5],
            )
            self.session.broker_uri = urlunparse(uri)
        # Init protocol handler
        # if not self._handler:
        self._handler = ClientProtocolHandler(self.plugins_manager, loop=self._loop)

        if secure:
            sc = ssl.create_default_context(
                ssl.Purpose.SERVER_AUTH,
                cafile=self.session.cafile,
                capath=self.session.capath,
                cadata=self.session.cadata,
            )
            if "certfile" in self.config and "keyfile" in self.config:
                sc.load_cert_chain(self.config["certfile"], self.config["keyfile"])
            if "check_hostname" in self.config and isinstance(
                self.config["check_hostname"], bool
            ):
                sc.check_hostname = self.config["check_hostname"]
            kwargs["ssl"] = sc

        try:
            reader = None
            writer = None
            self._connected_state.clear()
            # Open connection
            if scheme in ("mqtt", "mqtts"):
                conn_reader, conn_writer = await asyncio.open_connection(
                    self.session.remote_address,
                    self.session.remote_port,
                    loop=self._loop,
                    **kwargs
                )
                reader = StreamReaderAdapter(conn_reader)
                writer = StreamWriterAdapter(conn_writer)
            elif scheme in ("ws", "wss"):
                websocket = await websockets.connect(
                    self.session.broker_uri,
                    subprotocols=["mqtt"],
                    loop=self._loop,
                    extra_headers=self.extra_headers,
                    **kwargs
                )
                reader = WebSocketsReader(websocket)
                writer = WebSocketsWriter(websocket)
            # Start MQTT protocol
            self._handler.attach(self.session, reader, writer)
            return_code = await self._handler.mqtt_connect()
            if return_code is not CONNECTION_ACCEPTED:
                self.session.transitions.disconnect()
                self.logger.warning("Connection rejected with code '%s'" % return_code)
                exc = ConnectException("Connection rejected by broker")
                exc.return_code = return_code
                raise exc
            else:
                # Handle MQTT protocol
                await self._handler.start()
                self.session.transitions.connect()
                self._connected_state.set()
                self.logger.debug(
                    "connected to %s:%s"
                    % (self.session.remote_address, self.session.remote_port)
                )
            return return_code
        except InvalidURI as iuri:
            self.logger.warning(
                "connection failed: invalid URI '%s'" % self.session.broker_uri
            )
            self.session.transitions.disconnect()
            raise ConnectException(
                "connection failed: invalid URI '%s'" % self.session.broker_uri, iuri
            )
        except InvalidHandshake as ihs:
            self.logger.warning("connection failed: invalid websocket handshake")
            self.session.transitions.disconnect()
            raise ConnectException(
                "connection failed: invalid websocket handshake", ihs
            )
        except (ProtocolHandlerException, ConnectionError, OSError) as e:
            self.logger.warning("MQTT connection failed: %r" % e)
            self.session.transitions.disconnect()
            raise ConnectException(e)

    async def handle_connection_close(self):
        def cancel_tasks():
            self._no_more_connections.set()
            while self.client_tasks:
                task = self.client_tasks.popleft()
                if not task.done():
                    task.set_exception(ClientException("Connection lost"))

        self.logger.debug("Watch broker disconnection")
        # Wait for disconnection from broker (like connection lost)
        await self._handler.wait_disconnect()
        self.logger.warning("Disconnected from broker")

        # Block client API
        self._connected_state.clear()

        # stop an clean handler
        # await self._handler.stop()
        self._handler.detach()
        self.session.transitions.disconnect()

        if self.config.get("auto_reconnect", False):
            # Try reconnection
            self.logger.debug("Auto-reconnecting")
            try:
                await self.reconnect()
            except ConnectException:
                # Cancel client pending tasks
                cancel_tasks()
        else:
            # Cancel client pending tasks
            cancel_tasks()

    def _initsession(
        self, uri=None, cleansession=None, cafile=None, capath=None, cadata=None
    ) -> Session:
        # Load config
        broker_conf = self.config.get("broker", dict()).copy()
        if uri:
            broker_conf["uri"] = uri
        if cafile:
            broker_conf["cafile"] = cafile
        elif "cafile" not in broker_conf:
            broker_conf["cafile"] = None
        if capath:
            broker_conf["capath"] = capath
        elif "capath" not in broker_conf:
            broker_conf["capath"] = None
        if cadata:
            broker_conf["cadata"] = cadata
        elif "cadata" not in broker_conf:
            broker_conf["cadata"] = None

        if cleansession is not None:
            broker_conf["cleansession"] = cleansession

        if not broker_conf.get("uri"):
            raise ClientException("Missing connection parameter 'uri'")

        s = Session()
        s.broker_uri = broker_conf["uri"]
        s.client_id = self.client_id
        s.cafile = broker_conf["cafile"]
        s.capath = broker_conf["capath"]
        s.cadata = broker_conf["cadata"]
        if cleansession is not None:
            s.clean_session = cleansession
        else:
            s.clean_session = self.config.get("cleansession", True)
        s.keep_alive = self.config["keep_alive"] - self.config["ping_delay"]
        if "will" in self.config:
            s.will_flag = True
            s.will_retain = self.config["will"]["retain"]
            s.will_topic = self.config["will"]["topic"]
            s.will_message = self.config["will"]["message"]
            s.will_qos = self.config["will"]["qos"]
        else:
            s.will_flag = False
            s.will_retain = False
            s.will_topic = None
            s.will_message = None
        return s
