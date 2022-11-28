# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import asyncio
from asyncio import futures
from amqtt.mqtt.protocol.handler import ProtocolHandler, EVENT_MQTT_PACKET_RECEIVED
from amqtt.mqtt.disconnect import DisconnectPacket
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.pingresp import PingRespPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.unsubscribe import UnsubscribePacket
from amqtt.mqtt.unsuback import UnsubackPacket
from amqtt.mqtt.connect import ConnectVariableHeader, ConnectPayload, ConnectPacket
from amqtt.mqtt.connack import ConnackPacket
from amqtt.session import Session
from amqtt.plugins.manager import PluginManager


class ClientProtocolHandler(ProtocolHandler):
    def __init__(
        self, plugins_manager: PluginManager, session: Session = None, loop=None
    ):
        super().__init__(plugins_manager, session, loop=loop)
        self._ping_task = None
        self._pingresp_queue = asyncio.Queue()
        self._subscriptions_waiter = dict()
        self._unsubscriptions_waiter = dict()
        self._disconnect_waiter = futures.Future()

    async def start(self):
        await super().start()
        if self._disconnect_waiter.cancelled():
            self._disconnect_waiter = futures.Future()

    async def stop(self):
        await super().stop()
        if self._ping_task and not self._ping_task.cancelled():
            self.logger.debug("Cancel ping task")
            self._ping_task.cancel()

        if not self._disconnect_waiter.done():
            self._disconnect_waiter.cancel()

    def _build_connect_packet(self):
        vh = ConnectVariableHeader()
        payload = ConnectPayload()

        vh.keep_alive = self.session.keep_alive
        vh.clean_session_flag = self.session.clean_session
        vh.will_retain_flag = self.session.will_retain
        payload.client_id = self.session.client_id

        if self.session.username:
            vh.username_flag = True
            payload.username = self.session.username
        else:
            vh.username_flag = False

        if self.session.password:
            vh.password_flag = True
            payload.password = self.session.password
        else:
            vh.password_flag = False
        if self.session.will_flag:
            vh.will_flag = True
            vh.will_qos = self.session.will_qos
            payload.will_message = self.session.will_message
            payload.will_topic = self.session.will_topic
        else:
            vh.will_flag = False

        packet = ConnectPacket(vh=vh, payload=payload)
        return packet

    async def mqtt_connect(self):
        connect_packet = self._build_connect_packet()
        await self._send_packet(connect_packet)
        connack = await ConnackPacket.from_stream(self.reader)
        await self.plugins_manager.fire_event(
            EVENT_MQTT_PACKET_RECEIVED, packet=connack, session=self.session
        )
        return connack.return_code

    def handle_write_timeout(self):
        try:
            if not self._ping_task:
                self.logger.debug("Scheduling Ping")
                self._ping_task = asyncio.ensure_future(self.mqtt_ping())
        except Exception as e:
            self.logger.debug("Exception ignored in ping task: %r" % e)

    def handle_read_timeout(self):
        pass

    async def mqtt_subscribe(self, topics, packet_id):
        """
        :param topics: array of topics [{'filter':'/a/b', 'qos': 0x00}, ...]
        :return:
        """

        # Build and send SUBSCRIBE message
        subscribe = SubscribePacket.build(topics, packet_id)
        await self._send_packet(subscribe)

        # Wait for SUBACK is received
        waiter = futures.Future()
        self._subscriptions_waiter[subscribe.variable_header.packet_id] = waiter
        return_codes = await waiter

        del self._subscriptions_waiter[subscribe.variable_header.packet_id]
        return return_codes

    async def handle_suback(self, suback: SubackPacket):
        packet_id = suback.variable_header.packet_id
        try:
            waiter = self._subscriptions_waiter.get(packet_id)
            waiter.set_result(suback.payload.return_codes)
        except KeyError:
            self.logger.warning(
                "Received SUBACK for unknown pending subscription with Id: %s"
                % packet_id
            )

    async def mqtt_unsubscribe(self, topics, packet_id):
        """

        :param topics: array of topics ['/a/b', ...]
        :return:
        """
        unsubscribe = UnsubscribePacket.build(topics, packet_id)
        await self._send_packet(unsubscribe)
        waiter = futures.Future()
        self._unsubscriptions_waiter[unsubscribe.variable_header.packet_id] = waiter
        await waiter
        del self._unsubscriptions_waiter[unsubscribe.variable_header.packet_id]

    async def handle_unsuback(self, unsuback: UnsubackPacket):
        packet_id = unsuback.variable_header.packet_id
        try:
            waiter = self._unsubscriptions_waiter.get(packet_id)
            waiter.set_result(None)
        except KeyError:
            self.logger.warning(
                "Received UNSUBACK for unknown pending subscription with Id: %s"
                % packet_id
            )

    async def mqtt_disconnect(self):
        disconnect_packet = DisconnectPacket()
        await self._send_packet(disconnect_packet)

    async def mqtt_ping(self):
        ping_packet = PingReqPacket()
        await self._send_packet(ping_packet)
        resp = await self._pingresp_queue.get()
        if self._ping_task:
            self._ping_task = None
        return resp

    async def handle_pingresp(self, pingresp: PingRespPacket):
        await self._pingresp_queue.put(pingresp)

    async def handle_connection_closed(self):
        self.logger.debug("Broker closed connection")
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def wait_disconnect(self):
        await self._disconnect_waiter
