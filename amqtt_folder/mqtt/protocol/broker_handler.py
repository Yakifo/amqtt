# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from asyncio import futures, Queue
from amqtt.mqtt.protocol.handler import ProtocolHandler
from amqtt.mqtt.connack import (
    CONNECTION_ACCEPTED,
    UNACCEPTABLE_PROTOCOL_VERSION,
    IDENTIFIER_REJECTED,
    BAD_USERNAME_PASSWORD,
    NOT_AUTHORIZED,
    ConnackPacket,
)
from amqtt.mqtt.connect import ConnectPacket
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.pingresp import PingRespPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.unsubscribe import UnsubscribePacket
from amqtt.mqtt.unsuback import UnsubackPacket
from amqtt.utils import format_client_message
from amqtt.session import Session
from amqtt.plugins.manager import PluginManager
from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.errors import MQTTException
from .handler import EVENT_MQTT_PACKET_RECEIVED, EVENT_MQTT_PACKET_SENT


class BrokerProtocolHandler(ProtocolHandler):
    def __init__(
        self, plugins_manager: PluginManager, session: Session = None, loop=None
    ):
        super().__init__(plugins_manager, session, loop)
        self._disconnect_waiter = None
        self._pending_subscriptions = Queue()
        self._pending_unsubscriptions = Queue()

    async def start(self):
        await super().start()
        if self._disconnect_waiter is None:
            self._disconnect_waiter = futures.Future()

    async def stop(self):
        await super().stop()
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def wait_disconnect(self):
        return await self._disconnect_waiter

    def handle_write_timeout(self):
        pass

    def handle_read_timeout(self):
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def handle_disconnect(self, disconnect):
        self.logger.debug("Client disconnecting")
        if self._disconnect_waiter and not self._disconnect_waiter.done():
            self.logger.debug("Setting waiter result to %r" % disconnect)
            self._disconnect_waiter.set_result(disconnect)

    async def handle_connection_closed(self):
        await self.handle_disconnect(None)

    async def handle_connect(self, connect: ConnectPacket):
        # Broker handler shouldn't received CONNECT message during messages handling
        # as CONNECT messages are managed by the broker on client connection
        self.logger.error(
            "%s [MQTT-3.1.0-2] %s : CONNECT message received during messages handling"
            % (self.session.client_id, format_client_message(self.session))
        )
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def handle_pingreq(self, pingreq: PingReqPacket):
        await self._send_packet(PingRespPacket.build())

    async def handle_subscribe(self, subscribe: SubscribePacket):
        subscription = {
            "packet_id": subscribe.variable_header.packet_id,
            "topics": subscribe.payload.topics,
        }
        await self._pending_subscriptions.put(subscription)

    async def handle_unsubscribe(self, unsubscribe: UnsubscribePacket):
        unsubscription = {
            "packet_id": unsubscribe.variable_header.packet_id,
            "topics": unsubscribe.payload.topics,
        }
        await self._pending_unsubscriptions.put(unsubscription)

    async def get_next_pending_subscription(self):
        subscription = await self._pending_subscriptions.get()
        return subscription

    async def get_next_pending_unsubscription(self):
        unsubscription = await self._pending_unsubscriptions.get()
        return unsubscription

    async def mqtt_acknowledge_subscription(self, packet_id, return_codes):
        suback = SubackPacket.build(packet_id, return_codes)
        await self._send_packet(suback)

    async def mqtt_acknowledge_unsubscription(self, packet_id):
        unsuback = UnsubackPacket.build(packet_id)
        await self._send_packet(unsuback)

    async def mqtt_connack_authorize(self, authorize: bool):
        if authorize:
            connack = ConnackPacket.build(self.session.parent, CONNECTION_ACCEPTED)
        else:
            connack = ConnackPacket.build(self.session.parent, NOT_AUTHORIZED)
        await self._send_packet(connack)

    @classmethod
    async def init_from_connect(
        cls, reader: ReaderAdapter, writer: WriterAdapter, plugins_manager, loop=None
    ):
        """

        :param reader:
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
            raise MQTTException("[[MQTT-3.1.3-3]] : Client identifier must be present")

        if connect.variable_header.will_flag:
            if (
                connect.payload.will_topic is None
                or connect.payload.will_message is None
            ):
                raise MQTTException(
                    "will flag set, but will topic/message not present in payload"
                )

        if connect.variable_header.reserved_flag:
            raise MQTTException("[MQTT-3.1.2-3] CONNECT reserved flag must be set to 0")
        if connect.proto_name != "MQTT":
            raise MQTTException(
                '[MQTT-3.1.2-1] Incorrect protocol name: "%s"' % connect.proto_name
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
                0, UNACCEPTABLE_PROTOCOL_VERSION
            )  # [MQTT-3.2.2-4] session_parent=0
        elif not connect.username_flag and connect.password_flag:
            connack = ConnackPacket.build(0, BAD_USERNAME_PASSWORD)  # [MQTT-3.1.2-22]
        elif connect.username_flag and connect.username is None:
            error_msg = "Invalid username from %s" % (
                format_client_message(address=remote_address, port=remote_port)
            )
            connack = ConnackPacket.build(
                0, BAD_USERNAME_PASSWORD
            )  # [MQTT-3.2.2-4] session_parent=0
        elif connect.password_flag and connect.password is None:
            error_msg = "Invalid password %s" % (
                format_client_message(address=remote_address, port=remote_port)
            )
            connack = ConnackPacket.build(
                0, BAD_USERNAME_PASSWORD
            )  # [MQTT-3.2.2-4] session_parent=0
        elif connect.clean_session_flag is False and (
            connect.payload.client_id_is_random
        ):
            error_msg = (
                "[MQTT-3.1.3-8] [MQTT-3.1.3-9] %s: No client Id provided (cleansession=0)"
                % (format_client_message(address=remote_address, port=remote_port))
            )
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
