from asyncio import Queue
from collections import OrderedDict
import logging
from math import floor
import time
from typing import TYPE_CHECKING, Any, ClassVar

from transitions import Machine

from amqtt.constants import MQTT_PROTOCOL_LEVEL_3_1_1
from amqtt.errors import AMQTTError
from amqtt.mqtt3.publish import PublishPacket

OUTGOING = 0
INCOMING = 1

MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL = 0
MQTT5_SESSION_EXPIRY_NEVER = 0xFFFF_FFFF
MQTT5_DEFAULT_RECEIVE_MAXIMUM = 65_535
MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM = 0

if TYPE_CHECKING:
    import ssl

logger = logging.getLogger(__name__)


class ApplicationMessage:
    """ApplicationMessage and subclasses are used to store published message information flow.

    These objects can contain different information depending on the way they were created (incoming or outgoing)
    and the quality of service used between peers.
    """

    __slots__ = (
        "data",
        "packet_id",
        "puback_packet",
        "pubcomp_packet",
        "publish_packet",
        "pubrec_packet",
        "pubrel_packet",
        "qos",
        "retain",
        "topic",
    )

    def __init__(self, packet_id: int | None, topic: str, qos: int | None, data: bytes | bytearray, retain: bool) -> None:
        self.packet_id: int | None = packet_id
        """ Publish message packet identifier
            <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718025>_
        """

        self.topic: str = topic
        """ Publish message topic"""

        self.qos: int | None = qos
        """ Publish message Quality of Service"""

        self.data: bytes | bytearray = data
        """ Publish message payload data"""

        self.retain: bool = retain
        """ Publish message retain flag"""

        self.publish_packet: PublishPacket | None = None
        """ :class:`amqtt.mqtt.publish.PublishPacket` instance corresponding to the
        `PUBLISH <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718037>`_ packet in the messages flow.
        ``None`` if the PUBLISH packet has not already been received or sent."""

        self.puback_packet: Any | None = None
        """ :class:`amqtt.mqtt.puback.PubackPacket` instance corresponding to the
        `PUBACK <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718043>`_ packet in the messages flow.
        ``None`` if QoS != QOS_1 or if the PUBACK packet has not already been received or sent."""

        self.pubrec_packet: Any | None = None
        """ :class:`amqtt.mqtt.puback.PubrecPacket` instance corresponding to the
        `PUBREC <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718048>`_ packet in the messages flow.
        ``None`` if QoS != QOS_2 or if the PUBREC packet has not already been received or sent."""

        self.pubrel_packet: Any | None = None
        """ :class:`amqtt.mqtt.puback.PubrelPacket` instance corresponding to the
        `PUBREL <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718053>`_ packet in the messages flow.
        ``None`` if QoS != QOS_2 or if the PUBREL packet has not already been received or sent."""

        self.pubcomp_packet: Any | None = None
        """ :class:`amqtt.mqtt.puback.PubrelPacket` instance corresponding to the
        `PUBCOMP <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718058>`_ packet in the messages flow.
        ``None`` if QoS != QOS_2 or if the PUBCOMP packet has not already been received or sent."""

    def build_publish_packet(self, dup: bool = False) -> PublishPacket:
        """Build :class:`amqtt.mqtt.publish.PublishPacket` from attributes.

        :param dup: force dup flag
        :return: :class:`amqtt.mqtt.publish.PublishPacket` built from ApplicationMessage instance attributes
        """
        return PublishPacket.build(self.topic, bytes(self.data), self.packet_id, dup, self.qos, self.retain)

    def __eq__(self, other: object) -> bool:
        """Compare two ApplicationMessage instances based on their packet_id.

        This method is used to check if two messages are the same based on their packet_id.
        :param other: The other ApplicationMessage instance to compare with.
        :return: True if the packet_id of both messages are equal, False otherwise.
        """
        if not isinstance(other, ApplicationMessage):
            return False
        return self.packet_id == other.packet_id


class IncomingApplicationMessage(ApplicationMessage):
    """Incoming :class:~amqtt.session.ApplicationMessage."""

    __slots__ = ("direction",)

    def __init__(self, packet_id: int | None, topic: str, qos: int | None, data: bytes, retain: bool) -> None:
        super().__init__(packet_id, topic, qos, data, retain)
        self.direction: int = INCOMING


class OutgoingApplicationMessage(ApplicationMessage):
    """Outgoing :class:~amqtt.session.ApplicationMessage."""

    __slots__ = ("direction",)

    def __init__(self, packet_id: int | None, topic: str, qos: int | None, data: bytes | bytearray, retain: bool) -> None:
        super().__init__(packet_id, topic, qos, data, retain)
        self.direction: int = OUTGOING


class Session:
    """MQTT session state shared by broker and client handlers.

    The negotiated protocol version is stored here for state and diagnostics.
    Prefer implementing protocol-specific behavior in the MQTT 3.1.1 and
    MQTT 5.0 protocol handler classes instead of scattering `mqtt_version`
    conditionals through shared broker, client, or session logic.

    Attributes:
        mqtt_version: Negotiated MQTT protocol level. Defaults to 4 for MQTT 3.1.1.
        states: Valid lifecycle state names for the session state machine.
        transitions: State machine that manages `new`, `connected`, and `disconnected` lifecycle states.
        remote_address: Peer address for the active connection, when known.
        remote_port: Peer port for the active connection, when known.
        client_id: MQTT client identifier associated with this session.
        clean_session: MQTT 3.1.1 clean-session flag from the CONNECT packet.
        will_flag: Whether the client registered a Will Message.
        will_message: Will Message payload.
        will_qos: Will Message QoS.
        will_retain: Will Message retain flag.
        will_topic: Will Message topic.
        keep_alive: Negotiated keep-alive interval in seconds.
        publish_retry_delay: Delay used before retrying unacknowledged outgoing publishes.
        broker_uri: Broker URI used by client-side sessions.
        username: Username supplied during CONNECT, when present.
        password: Password supplied during CONNECT, when present.
        cafile: CA certificate file path used by client-side TLS connections.
        capath: CA certificate directory path used by client-side TLS connections.
        cadata: CA certificate data used by client-side TLS connections.
        _packet_id: Internal packet identifier counter used by `next_packet_id`.
        parent: CONNACK session-present flag state used by broker handlers.
        last_connect_time: Unix timestamp for the most recent connected transition.
        ssl_object: TLS object for the active connection, when available.
        last_disconnect_time: Unix timestamp for the most recent disconnected transition.
        session_expiry_interval: MQTT 5 session expiry in seconds. Defaults to 0. [MQTT-3.1.2.11.2]
        receive_maximum: MQTT 5 maximum concurrent QoS 1/2 incoming publishes. Defaults to 65,535. [MQTT-3.1.2.11.3]
        topic_alias_maximum: MQTT 5 maximum accepted topic alias. Defaults to 0, disabling aliases. [MQTT-3.1.2.11.5]
        topic_alias_map: MQTT 5 per-session alias-to-topic mapping.
        subscription_identifiers: MQTT 5 topic filter to subscription identifier mapping.
        inflight_qos2_count: MQTT 5 flow-control counter for in-flight QoS 2 messages.
        maximum_packet_size: MQTT 5 maximum accepted packet size, or None for unlimited. [MQTT-3.1.2.11.4]
        inflight_out: Outgoing QoS messages currently in protocol flow.
        inflight_in: Incoming QoS messages currently in protocol flow.
        retained_messages: Offline messages retained for this session.
        delivered_message_queue: Incoming application messages ready for broker/client processing.
        is_anonymous: Whether this session belongs to an anonymous or generated-identifier client.

    """

    states: ClassVar[list[str]] = ["new", "connected", "disconnected"]

    def __init__(self) -> None:
        self._init_states()

        self.mqtt_version: int = MQTT_PROTOCOL_LEVEL_3_1_1

        self.remote_address: str | None = None
        self.remote_port: int | None = None
        self.client_id: str | None = None
        self.clean_session: bool | None = None
        self.will_flag: bool = False
        self.will_message: bytes | bytearray | None = None
        self.will_qos: int | None = None
        self.will_retain: bool | None = None
        self.will_topic: str | None = None
        self.keep_alive: int = 0
        self.publish_retry_delay: int = 0
        self.broker_uri: str | None = None
        self.username: str | None = None
        self.password: str | None = None
        self.cafile: str | None = None
        self.capath: str | None = None
        self.cadata: bytes | None = None
        self._packet_id: int = 0
        self.parent: int = 0
        self.last_connect_time: int | None = None
        self.ssl_object: ssl.SSLObject | None = None
        self.last_disconnect_time: int | None = None

        # MQTT 5.0 session properties.
        self.session_expiry_interval: int = MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL
        self.receive_maximum: int = MQTT5_DEFAULT_RECEIVE_MAXIMUM
        self.topic_alias_maximum: int = MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM
        self.topic_alias_map: dict[int, str] = {}
        self.subscription_identifiers: dict[str, int] = {}
        self.inflight_qos2_count: int = 0
        self.maximum_packet_size: int | None = None

        # Used to store outgoing ApplicationMessage while publish protocol flows
        self.inflight_out: OrderedDict[int, OutgoingApplicationMessage] = OrderedDict()

        # Used to store incoming ApplicationMessage while publish protocol flows
        self.inflight_in: OrderedDict[int, IncomingApplicationMessage] = OrderedDict()

        # Stores messages retained for this session (specifically when the client is disconnected)
        self.retained_messages: Queue[ApplicationMessage] = Queue()

        # Stores PUBLISH messages ID received in order and ready for application process
        self.delivered_message_queue: Queue[ApplicationMessage] = Queue()

        # identify anonymous client sessions or clients which didn't identify themselves
        self.is_anonymous: bool = False

    def _init_states(self) -> None:
        self.transitions = Machine(states=Session.states, initial="new")
        self.transitions.add_transition(
            trigger="connect",
            source="new",
            dest="connected",
        )
        self.transitions.on_enter_connected(self._on_enter_connected)
        self.transitions.add_transition(
            trigger="connect",
            source="disconnected",
            dest="connected",
        )
        self.transitions.add_transition(
            trigger="disconnect",
            source="connected",
            dest="disconnected",
        )
        self.transitions.on_enter_disconnected(self._on_enter_disconnected)
        self.transitions.add_transition(
            trigger="disconnect",
            source="new",
            dest="disconnected",
        )
        self.transitions.add_transition(
            trigger="disconnect",
            source="disconnected",
            dest="disconnected",
        )

    def _on_enter_connected(self) -> None:
        cur_time = floor(time.time())
        if self.last_disconnect_time is not None:
            logger.debug(f"Session reconnected after {cur_time - self.last_disconnect_time} seconds.")

        self.last_connect_time = cur_time
        self.last_disconnect_time = None

    def _on_enter_disconnected(self) -> None:
        cur_time = floor(time.time())
        if self.last_connect_time is not None:
            logger.debug(f"Session disconnected after {cur_time - self.last_connect_time} seconds.")
        self.last_disconnect_time = cur_time

    @property
    def next_packet_id(self) -> int:
        self._packet_id = (self._packet_id % 65535) + 1
        limit = self._packet_id
        while self._packet_id in self.inflight_in or self._packet_id in self.inflight_out:
            self._packet_id = (self._packet_id % 65535) + 1
            if self._packet_id == limit:
                msg = "More than 65535 messages pending. No free packet ID"
                raise AMQTTError(msg)

        return self._packet_id

    @property
    def inflight_in_count(self) -> int:
        return len(self.inflight_in)

    @property
    def inflight_out_count(self) -> int:
        return len(self.inflight_out)

    @property
    def retained_messages_count(self) -> int:
        return self.retained_messages.qsize()

    def __repr__(self) -> str:
        """Return a string representation of the session.

        This method is used for debugging and logging purposes.
        It includes the client ID and the current state of the session.
        """
        return type(self).__name__ + f"(clientId={self.client_id}, state={self.transitions.state})"

    def __getstate__(self) -> dict[str, Any]:
        """Return the state of the session for pickling.

        This method is called when pickling the session object.
        It returns a dictionary containing the session's state, excluding
        unpicklable entries.
        """
        state = self.__dict__.copy()
        # Remove the unpicklable entries.
        del state["retained_messages"]
        del state["delivered_message_queue"]
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore the session from its state.

        This method is called when unpickling the session object.
        It restores the session's state and reinitializes the queues.
        """
        self.__dict__.update(state)
        self.retained_messages = Queue()
        self.delivered_message_queue = Queue()

    def clear_queues(self) -> None:
        """Clear all message queues associated with the session."""
        while not self.retained_messages.empty():
            self.retained_messages.get_nowait()
        while not self.delivered_message_queue.empty():
            self.delivered_message_queue.get_nowait()

    def __eq__(self, other: object) -> bool:
        """Compare two Session instances based on their client_id."""
        if not isinstance(other, Session):
            return False
        return self.client_id == other.client_id
