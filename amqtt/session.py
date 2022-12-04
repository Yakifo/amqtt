# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from asyncio import Queue
from typing import Optional, OrderedDict, Union

from transitions import Machine  # type: ignore

from amqtt.mqtt.publish import PublishPacket
from amqtt.mqtt.puback import PubackPacket
from amqtt.mqtt.pubrec import PubrecPacket
from amqtt.mqtt.pubrel import PubrelPacket
from amqtt.mqtt.pubcomp import PubcompPacket
from amqtt.errors import AMQTTException

OUTGOING = 0
INCOMING = 1


class ApplicationMessage:

    """
    ApplicationMessage and subclasses are used to store published message information flow. These objects can contain different information depending on the way they were created (incoming or outgoing) and the quality of service used between peers.
    """

    __slots__ = (
        "packet_id",
        "topic",
        "qos",
        "data",
        "retain",
        "publish_packet",
        "puback_packet",
        "pubrec_packet",
        "pubrel_packet",
        "pubcomp_packet",
    )

    packet_id: int
    topic: str
    qos: int
    data: bytes
    retain: bool
    publish_packet: Optional[PublishPacket]
    puback_packet: Optional[PubackPacket]
    pubrec_packet: Optional[PubrecPacket]
    pubrel_packet: Optional[PubrelPacket]
    pubcomp_packet: Optional[PubcompPacket]

    def __init__(self, packet_id: int, topic: str, qos: int, data: bytes, retain: bool):
        self.packet_id = packet_id
        """ Publish message `packet identifier <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718025>`_"""

        self.topic = topic
        """ Publish message topic"""

        self.qos = qos
        """ Publish message Quality of Service"""

        self.data = data
        """ Publish message payload data"""

        self.retain = retain
        """ Publish message retain flag"""

        self.publish_packet: Optional[PublishPacket] = None
        """ :class:`amqtt.mqtt.publish.PublishPacket` instance corresponding to the `PUBLISH <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718037>`_ packet in the messages flow. ``None`` if the PUBLISH packet has not already been received or sent."""

        self.puback_packet: Optional[PubackPacket] = None
        """ :class:`amqtt.mqtt.puback.PubackPacket` instance corresponding to the `PUBACK <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718043>`_ packet in the messages flow. ``None`` if QoS != QOS_1 or if the PUBACK packet has not already been received or sent."""

        self.pubrec_packet: Optional[PubrecPacket] = None
        """ :class:`amqtt.mqtt.puback.PubrecPacket` instance corresponding to the `PUBREC <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718048>`_ packet in the messages flow. ``None`` if QoS != QOS_2 or if the PUBREC packet has not already been received or sent."""

        self.pubrel_packet: Optional[PubrelPacket] = None
        """ :class:`amqtt.mqtt.puback.PubrelPacket` instance corresponding to the `PUBREL <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718053>`_ packet in the messages flow. ``None`` if QoS != QOS_2 or if the PUBREL packet has not already been received or sent."""

        self.pubcomp_packet: Optional[PubcompPacket] = None
        """ :class:`amqtt.mqtt.puback.PubrelPacket` instance corresponding to the `PUBCOMP <http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718058>`_ packet in the messages flow. ``None`` if QoS != QOS_2 or if the PUBCOMP packet has not already been received or sent."""

    def build_publish_packet(self, dup: bool = False) -> PublishPacket:
        """
            Build :class:`amqtt.mqtt.publish.PublishPacket` from attributes

        :param dup: force dup flag
        :return: :class:`amqtt.mqtt.publish.PublishPacket` built from ApplicationMessage instance attributes
        """
        return PublishPacket.build(
            self.topic, self.data, self.packet_id, dup, self.qos, self.retain
        )

    def __eq__(self, other):
        return self.packet_id == other.packet_id


class IncomingApplicationMessage(ApplicationMessage):

    """
    Incoming :class:`~amqtt.session.ApplicationMessage`.
    """

    __slots__ = ("direction",)

    direction: int

    def __init__(self, packet_id: int, topic: str, qos, data, retain):
        super().__init__(packet_id, topic, qos, data, retain)
        self.direction = INCOMING


class OutgoingApplicationMessage(ApplicationMessage):

    """
    Outgoing :class:`~amqtt.session.ApplicationMessage`.
    """

    __slots__ = ("direction",)

    direction: int

    def __init__(self, packet_id: int, topic, qos, data, retain):
        super().__init__(packet_id, topic, qos, data, retain)
        self.direction = OUTGOING


class Session:
    states = ["new", "connected", "disconnected"]

    remote_address: Optional[str] = None
    remote_port: Optional[int] = None
    client_id: Optional[str] = None
    clean_session: Optional[bool] = None
    will_flag: bool = False
    will_message: Union[bytes, bytearray, None] = None
    will_qos: Optional[int] = None
    will_retain: Optional[bool] = None
    will_topic: Optional[str] = None
    keep_alive: int = 0
    publish_retry_delay: int = 0
    broker_uri: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    cafile: Optional[str] = None
    capath: Optional[str] = None
    cadata = None
    _packet_id: int = 0
    parent: int = 0

    inflight_out: OrderedDict[int, ApplicationMessage]
    inflight_in: OrderedDict[int, ApplicationMessage]
    retained_messages: Queue[ApplicationMessage]
    delivered_message_queue: Queue[ApplicationMessage]

    def __init__(self):
        self._init_states()
        self.remote_address = None
        self.remote_port = None
        self.client_id = None
        self.clean_session = None
        self.will_flag = False
        self.will_message = None
        self.will_qos = None
        self.will_retain = None
        self.will_topic = None
        self.keep_alive = 0
        self.publish_retry_delay = 0
        self.broker_uri = None
        self.username = None
        self.password = None
        self.cafile = None
        self.capath = None
        self.cadata = None
        self._packet_id = 0
        self.parent = 0

        # Used to store outgoing ApplicationMessage while publish protocol flows
        self.inflight_out = OrderedDict()

        # Used to store incoming ApplicationMessage while publish protocol flows
        self.inflight_in = OrderedDict()

        # Stores messages retained for this session
        self.retained_messages = Queue()

        # Stores PUBLISH messages ID received in order and ready for application process
        self.delivered_message_queue = Queue()

    def _init_states(self):
        self.transitions = Machine(states=Session.states, initial="new")
        self.transitions.add_transition(
            trigger="connect", source="new", dest="connected"
        )
        self.transitions.add_transition(
            trigger="connect", source="disconnected", dest="connected"
        )
        self.transitions.add_transition(
            trigger="disconnect", source="connected", dest="disconnected"
        )
        self.transitions.add_transition(
            trigger="disconnect", source="new", dest="disconnected"
        )
        self.transitions.add_transition(
            trigger="disconnect", source="disconnected", dest="disconnected"
        )

    @property
    def next_packet_id(self) -> int:
        self._packet_id += 1
        if self._packet_id > 65535:
            self._packet_id = 1
        while (
            self._packet_id in self.inflight_in or self._packet_id in self.inflight_out
        ):
            self._packet_id += 1
            if self._packet_id > 65535:
                raise AMQTTException(
                    "More than 65525 messages pending. No free packet ID"
                )

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

    def __repr__(self):
        return type(self).__name__ + "(clientId={}, state={})".format(
            self.client_id, self.transitions.state
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        # Remove the unpicklable entries.
        # del state['transitions']
        del state["retained_messages"]
        del state["delivered_message_queue"]
        return state

    def __setstate(self, state):
        self.__dict__.update(state)
        self.retained_messages = Queue()
        self.delivered_message_queue = Queue()

    def __eq__(self, other):
        return self.client_id == other.client_id
