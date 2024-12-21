# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from asyncio import AbstractEventLoop, Queue, futures

from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.errors import MQTTException
from amqtt.mqtt.connack import (
    BAD_USERNAME_PASSWORD,
    CONNECTION_ACCEPTED,
    IDENTIFIER_REJECTED,
    NOT_AUTHORIZED,
    UNACCEPTABLE_PROTOCOL_VERSION,
    ConnackPacket,
)
from amqtt.mqtt.connect import ConnectPacket
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.pingresp import PingRespPacket
from amqtt.mqtt.protocol.handler import ProtocolHandler
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.mqtt.unsuback import UnsubackPacket
from amqtt.mqtt.unsubscribe import UnsubscribePacket
from amqtt.plugins.manager import PluginManager
from amqtt.session import Session
from amqtt.utils import format_client_message

from .handler import EVENT_MQTT_PACKET_RECEIVED, EVENT_MQTT_PACKET_SENT


class BrokerProtocolHandler(ProtocolHandler):
    def __init__(
        self,
        plugins_manager: PluginManager,
        session: Session | None = None,
        loop: AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(plugins_manager, session, loop)
        self._disconnect_waiter = None
        self._pending_subscriptions = Queue()
        self._pending_unsubscriptions = Queue()

    async def start(self) -> None:
        await super().start()
        if self._disconnect_waiter is None:
            self._disconnect_waiter = futures.Future()

    async def stop(self) -> None:
        await super().stop()
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def wait_disconnect(self):
        return await self._disconnect_waiter

    def handle_write_timeout(self) -> None:
        pass

    def handle_read_timeout(self) -> None:
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def handle_disconnect(self, disconnect) -> None:
        self.logger.debug("Client disconnecting")
        if self._disconnect_waiter and not self._disconnect_waiter.done():
            self.logger.debug(f"Setting waiter result to {disconnect!r}")
            self._disconnect_waiter.set_result(disconnect)

    async def handle_connection_closed(self) -> None:
        await self.handle_disconnect(None)

    async def handle_connect(self, connect: ConnectPacket) -> None:
        # Broker handler shouldn't received CONNECT message during messages handling
        # as CONNECT messages are managed by the broker on client connection
        self.logger.error(
            f"{self.session.client_id} [MQTT-3.1.0-2] {format_client_message(self.session)} : CONNECT message received during messages handling",
        )
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def handle_pingreq(self, pingreq: PingReqPacket) -> None:
        await self._send_packet(PingRespPacket.build())

    async def handle_subscribe(self, subscribe: SubscribePacket) -> None:
        subscription = {
            "packet_id": subscribe.variable_header.packet_id,
            "topics": subscribe.payload.topics,
        }
        await self._pending_subscriptions.put(subscription)

    async def handle_unsubscribe(self, unsubscribe: UnsubscribePacket) -> None:
        unsubscription = {
            "packet_id": unsubscribe.variable_header.packet_id,
            "topics": unsubscribe.payload.topics,
        }
        await self._pending_unsubscriptions.put(unsubscription)

    async def get_next_pending_subscription(self):
        return await self._pending_subscriptions.get()

    async def get_next_pending_unsubscription(self):
        return await self._pending_unsubscriptions.get()

    async def mqtt_acknowledge_subscription(self, packet_id, return_codes) -> None:
        suback = SubackPacket.build(packet_id, return_codes)
        await self._send_packet(suback)

    async def mqtt_acknowledge_unsubscription(self, packet_id) -> None:
        unsuback = UnsubackPacket.build(packet_id)
        await self._send_packet(unsuback)

    async def mqtt_connack_authorize(self, authorize: bool) -> None:
        if authorize:
            connack = ConnackPacket.build(self.session.parent, CONNECTION_ACCEPTED)
        else:
            connack = ConnackPacket.build(self.session.parent, NOT_AUTHORIZED)
        await self._send_packet(connack)

    @classmethod
    async def init_from_connect(
        cls,
        reader: ReaderAdapter,
        writer: WriterAdapter,
        plugins_manager,
        loop=None,
    ):
        """:param reader:
        :param writer:
        :param plugins_manager:
        :param loop:
        :return:
        """
        remote_address, remote_port = writer.get_peer_info()
        connect = await ConnectPacket.from_stream(reader)
        await plugins_manager.fire_event(EVENT_MQTT_PACKET_RECEIVED, packet=connect)
        # this shouldn't be required anymore since broker generates for each client a random client_id if not provided
        # [MQTT-3.1.3-6]
        if connect.payload.client_id is None:
            msg = "[[MQTT-3.1.3-3]] : Client identifier must be present"
            raise MQTTException(msg)

        if connect.variable_header.will_flag and (connect.payload.will_topic is None or connect.payload.will_message is None):
            msg = "will flag set, but will topic/message not present in payload"
            raise MQTTException(
                msg,
            )

        if connect.variable_header.reserved_flag:
            msg = "[MQTT-3.1.2-3] CONNECT reserved flag must be set to 0"
            raise MQTTException(msg)
        if connect.proto_name != "MQTT":
            msg = f'[MQTT-3.1.2-1] Incorrect protocol name: "{connect.proto_name}"'
            raise MQTTException(
                msg,
            )

        connack = None
        error_msg = None
        if connect.proto_level != 4:
            # only MQTT 3.1.1 supported
            error_msg = "Invalid protocol from %s: %d" % (
                format_client_message(address=remote_address, port=remote_port),
                connect.proto_level,
            )
            connack = ConnackPacket.build(
                0,
                UNACCEPTABLE_PROTOCOL_VERSION,
            )  # [MQTT-3.2.2-4] session_parent=0
        elif not connect.username_flag and connect.password_flag:
            connack = ConnackPacket.build(0, BAD_USERNAME_PASSWORD)  # [MQTT-3.1.2-22]
        elif connect.username_flag and connect.username is None:
            error_msg = f"Invalid username from {format_client_message(address=remote_address, port=remote_port)}"
            connack = ConnackPacket.build(
                0,
                BAD_USERNAME_PASSWORD,
            )  # [MQTT-3.2.2-4] session_parent=0
        elif connect.password_flag and connect.password is None:
            error_msg = f"Invalid password {format_client_message(address=remote_address, port=remote_port)}"
            connack = ConnackPacket.build(
                0,
                BAD_USERNAME_PASSWORD,
            )  # [MQTT-3.2.2-4] session_parent=0
        elif connect.clean_session_flag is False and (connect.payload.client_id_is_random):
            error_msg = f"[MQTT-3.1.3-8] [MQTT-3.1.3-9] {format_client_message(address=remote_address, port=remote_port)}: No client Id provided (cleansession=0)"
            connack = ConnackPacket.build(0, IDENTIFIER_REJECTED)
        if connack is not None:
            await plugins_manager.fire_event(EVENT_MQTT_PACKET_SENT, packet=connack)
            await connack.to_stream(writer)
            await writer.close()
            raise MQTTException(error_msg)

        incoming_session = Session()
        incoming_session.client_id = connect.client_id
        incoming_session.clean_session = connect.clean_session_flag
        incoming_session.will_flag = connect.will_flag
        incoming_session.will_retain = connect.will_retain_flag
        incoming_session.will_qos = connect.will_qos
        incoming_session.will_topic = connect.will_topic
        incoming_session.will_message = connect.will_message
        incoming_session.username = connect.username
        incoming_session.password = connect.password
        if connect.keep_alive > 0:
            incoming_session.keep_alive = connect.keep_alive
        else:
            incoming_session.keep_alive = 0

        handler = cls(plugins_manager, loop=loop)
        return handler, incoming_session
