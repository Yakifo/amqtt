from __future__ import annotations

from typing import TYPE_CHECKING, Any

from amqtt.constants import MQTT_PROTOCOL_LEVEL_5
from amqtt.contexts import BrokerConfig
from amqtt.errors import MQTTError
from amqtt.events import MQTTEvents
from amqtt.mqtt3.protocol.handler import ProtocolHandler
from amqtt.mqtt5.connack import ConnackPacket
from amqtt.mqtt5.connect import ConnectPacket
from amqtt.mqtt5.properties import Properties
from amqtt.mqtt5.property_ids import (
    ASSIGNED_CLIENT_IDENTIFIER,
    MAXIMUM_PACKET_SIZE,
    MAXIMUM_QOS,
    PACKET_CONNACK,
    RECEIVE_MAXIMUM,
    RETAIN_AVAILABLE,
    SESSION_EXPIRY_INTERVAL,
    SHARED_SUBSCRIPTION_AVAILABLE,
    SUBSCRIPTION_IDENTIFIER_AVAILABLE,
    TOPIC_ALIAS_MAXIMUM,
    WILDCARD_SUBSCRIPTION_AVAILABLE,
)
from amqtt.mqtt5.reason_codes import ReasonCode
from amqtt.protocol import BrokerProtocolHandlerBase
from amqtt.session import (
    MQTT5_DEFAULT_RECEIVE_MAXIMUM,
    MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL,
    MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM,
    Session,
)

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from amqtt.adapters import ReaderAdapter, WriterAdapter
    from amqtt.broker import BrokerContext
    from amqtt.plugins.manager import PluginManager

_CONNECT_NOT_IMPLEMENTED = "MQTT 5 CONNECT handling is not implemented yet"
_PINGREQ_NOT_IMPLEMENTED = "MQTT 5 PINGREQ handling is not implemented yet"
_SUBSCRIBE_NOT_IMPLEMENTED = "MQTT 5 SUBSCRIBE handling is not implemented yet"
_UNSUBSCRIBE_NOT_IMPLEMENTED = "MQTT 5 UNSUBSCRIBE handling is not implemented yet"
_SUBACK_NOT_IMPLEMENTED = "MQTT 5 SUBACK handling is not implemented yet"
_UNSUBACK_NOT_IMPLEMENTED = "MQTT 5 UNSUBACK handling is not implemented yet"


class BrokerProtocolHandler(
    BrokerProtocolHandlerBase["BrokerContext"],
    ProtocolHandler["BrokerContext"],
):
    """Broker protocol handler selected for MQTT 5.0 connections."""

    def __init__(
        self,
        plugins_manager: PluginManager[BrokerContext],
        session: Session | None = None,
        loop: AbstractEventLoop | None = None,
        *,
        config: BrokerConfig | None = None,
    ) -> None:
        super().__init__(plugins_manager, session, loop)
        self.config = config if config is not None else BrokerConfig()
        self._init_broker_handler_state()

    async def start(self) -> None:
        await ProtocolHandler.start(self)
        self._start_broker_handler()

    async def stop(self) -> None:
        await ProtocolHandler.stop(self)
        self._stop_broker_handler()

    def handle_write_timeout(self) -> None:
        pass

    def handle_read_timeout(self) -> None:
        pass

    async def handle_connect(self, _connect: Any) -> None:
        raise MQTTError(_CONNECT_NOT_IMPLEMENTED)

    async def handle_pingreq(self, _pingreq: Any) -> None:
        raise MQTTError(_PINGREQ_NOT_IMPLEMENTED)

    async def handle_subscribe(self, _subscribe: Any) -> None:
        raise MQTTError(_SUBSCRIBE_NOT_IMPLEMENTED)

    async def handle_unsubscribe(self, _unsubscribe: Any) -> None:
        raise MQTTError(_UNSUBSCRIBE_NOT_IMPLEMENTED)

    async def mqtt_acknowledge_subscription(self, _packet_id: int, _return_codes: list[int]) -> None:
        raise MQTTError(_SUBACK_NOT_IMPLEMENTED)

    async def mqtt_acknowledge_unsubscription(self, _packet_id: int) -> None:
        raise MQTTError(_UNSUBACK_NOT_IMPLEMENTED)

    async def mqtt_connack_authorize(self, authorize: bool) -> None:
        if self.session is None:
            msg = "Session is not initialized!"
            raise MQTTError(msg)
        reason_code = ReasonCode.SUCCESS if authorize else ReasonCode.NOT_AUTHORIZED
        # [MQTT-3.2.2-6] CONNACK with a non-zero Reason Code must set Session Present to 0.
        session_present = bool(self.session.parent) if not reason_code.is_error() else False
        properties = self._build_success_connack_properties() if not reason_code.is_error() else None
        connack = ConnackPacket.build(session_present, reason_code, properties)
        await self._send_packet(connack)

    def _build_success_connack_properties(self) -> Properties:
        """Build the CONNACK properties advertised by the broker for accepted MQTT 5 connections."""
        if self.session is None:
            msg = "Session is not initialized!"
            raise MQTTError(msg)

        properties = Properties(packet_name=PACKET_CONNACK)
        properties.set(RECEIVE_MAXIMUM, self.config.receive_maximum)
        properties.set(TOPIC_ALIAS_MAXIMUM, self.config.topic_alias_maximum)

        if self.config.maximum_packet_size is not None:
            properties.set(MAXIMUM_PACKET_SIZE, self.config.maximum_packet_size)

        properties.set(RETAIN_AVAILABLE, int(self.config.retain_available))
        properties.set(WILDCARD_SUBSCRIPTION_AVAILABLE, int(self.config.wildcard_subscription_available))
        properties.set(SUBSCRIPTION_IDENTIFIER_AVAILABLE, int(self.config.subscription_identifier_available))
        properties.set(SHARED_SUBSCRIPTION_AVAILABLE, int(self.config.shared_subscription_available))

        if self.config.maximum_qos is not None:
            properties.set(MAXIMUM_QOS, self.config.maximum_qos)

        if self.session.client_id_is_generated and self.session.client_id:
            properties.set(ASSIGNED_CLIENT_IDENTIFIER, self.session.client_id)

        return properties

    @classmethod
    async def init_from_connect(
        cls,
        reader: ReaderAdapter,
        writer: WriterAdapter,
        plugins_manager: PluginManager[BrokerContext],
        loop: AbstractEventLoop | None = None,
        *,
        config: BrokerConfig | None = None,
    ) -> tuple[BrokerProtocolHandler, Session]:
        """Initialize a MQTT 5.0 broker handler from a CONNECT packet."""
        connect = await ConnectPacket.from_stream(reader)
        await plugins_manager.fire_event(MQTTEvents.PACKET_RECEIVED, packet=connect)

        if connect.variable_header is None:
            msg = "CONNECT packet: variable header not initialized."
            raise MQTTError(msg)
        if connect.payload is None:
            msg = "CONNECT packet: payload not initialized."
            raise MQTTError(msg)
        if connect.client_id is None:
            msg = "[MQTT-3.1.3-3] Client identifier must be present"
            raise MQTTError(msg)
        if connect.will_flag and (connect.will_topic is None or connect.will_message is None):
            msg = "[MQTT-3.1.2-9] Will flag set, but Will Topic or Will Payload not present"
            raise MQTTError(msg)

        remote_info = writer.get_peer_info()
        remote_address: str | None = None
        remote_port: int | None = None
        if remote_info is not None:
            remote_address, remote_port = remote_info

        incoming_session = Session()
        incoming_session.mqtt_version = MQTT_PROTOCOL_LEVEL_5
        incoming_session.client_id = connect.client_id
        # MQTT 5 Clean Start is kept in the existing clean_session field until
        # the broker session-expiry issue replaces the lifecycle semantics.
        incoming_session.clean_session = connect.clean_start_flag
        incoming_session.will_flag = connect.will_flag
        incoming_session.will_retain = connect.will_retain_flag
        incoming_session.will_qos = connect.will_qos
        incoming_session.will_topic = connect.will_topic
        incoming_session.will_message = connect.will_message
        incoming_session.username = connect.username
        incoming_session.password = (
            connect.password.decode("utf-8", errors="surrogateescape") if connect.password is not None else None
        )
        incoming_session.remote_address = remote_address
        incoming_session.remote_port = remote_port
        incoming_session.ssl_object = writer.get_ssl_info()
        incoming_session.keep_alive = max(connect.keep_alive, 0)

        incoming_session.session_expiry_interval = connect.properties.get_int(
            SESSION_EXPIRY_INTERVAL,
            MQTT5_DEFAULT_SESSION_EXPIRY_INTERVAL,
        )
        incoming_session.receive_maximum = connect.properties.get_int(
            RECEIVE_MAXIMUM,
            MQTT5_DEFAULT_RECEIVE_MAXIMUM,
        )
        incoming_session.topic_alias_maximum = connect.properties.get_int(
            TOPIC_ALIAS_MAXIMUM,
            MQTT5_DEFAULT_TOPIC_ALIAS_MAXIMUM,
        )
        incoming_session.maximum_packet_size = connect.properties.get_int(MAXIMUM_PACKET_SIZE)

        handler = cls(plugins_manager, loop=loop, config=config)
        return handler, incoming_session
