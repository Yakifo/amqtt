from asyncio import Queue
from collections import OrderedDict
from typing import Any, ClassVar

from transitions import Machine

from amqtt.errors import AMQTTError
from amqtt.mqtt.publish import PublishPacket

OUTGOING = 0
INCOMING = 1


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
    states: ClassVar[list[str]] = ["new", "connected", "disconnected"]

    def __init__(self) -> None:
        self._init_states()
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

        # Used to store outgoing ApplicationMessage while publish protocol flows
        self.inflight_out: OrderedDict[int, OutgoingApplicationMessage] = OrderedDict()

        # Used to store incoming ApplicationMessage while publish protocol flows
        self.inflight_in: OrderedDict[int, IncomingApplicationMessage] = OrderedDict()

        # Stores messages retained for this session
        self.retained_messages: Queue[ApplicationMessage] = Queue()

        # Stores PUBLISH messages ID received in order and ready for application process
        self.delivered_message_queue: Queue[ApplicationMessage] = Queue()

    def _init_states(self) -> None:
        self.transitions = Machine(states=Session.states, initial="new")
        self.transitions.add_transition(
            trigger="connect",
            source="new",
            dest="connected",
        )
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
