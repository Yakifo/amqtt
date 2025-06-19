import asyncio
from typing import TYPE_CHECKING, Any

from amqtt.errors import AMQTTError, NoDataError
from amqtt.events import MQTTEvents
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket, ConnectPayload, ConnectVariableHeader
from amqtt.mqtt.disconnect import DisconnectPacket
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.pingresp import PingRespPacket
from amqtt.mqtt.protocol.handler import ProtocolHandler
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.mqtt.unsuback import UnsubackPacket
from amqtt.mqtt.unsubscribe import UnsubscribePacket
from amqtt.plugins.manager import PluginManager
from amqtt.session import Session

if TYPE_CHECKING:
    from amqtt.client import ClientContext

class ClientProtocolHandler(ProtocolHandler["ClientContext"]):
    def __init__(
        self,
        plugins_manager: PluginManager["ClientContext"],
        session: Session | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(plugins_manager, session, loop=loop)
        self._ping_task: asyncio.Task[Any] | None = None
        self._pingresp_queue: asyncio.Queue[PingRespPacket] = asyncio.Queue()
        self._subscriptions_waiter: dict[int, asyncio.Future[list[int]]] = {}
        self._unsubscriptions_waiter: dict[int, asyncio.Future[Any]] = {}
        self._disconnect_waiter: asyncio.Future[Any] | None = asyncio.Future()

    async def start(self) -> None:
        await super().start()
        if self._disconnect_waiter and self._disconnect_waiter.cancelled():
            self._disconnect_waiter = asyncio.Future()

    async def stop(self) -> None:
        await super().stop()
        if self._ping_task and not self._ping_task.cancelled():
            self.logger.debug("Cancel ping task")
            self._ping_task.cancel()

        if self._disconnect_waiter and not self._disconnect_waiter.done():
            self._disconnect_waiter.cancel()

    def _build_connect_packet(self) -> ConnectPacket:
        vh = ConnectVariableHeader()
        payload = ConnectPayload()

        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)

        vh.keep_alive = self.session.keep_alive
        vh.clean_session_flag = self.session.clean_session if self.session.clean_session is not None else False
        vh.will_retain_flag = self.session.will_retain if self.session.will_retain is not None else False
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
            if self.session.will_qos is not None:
                vh.will_qos = self.session.will_qos
            payload.will_message = self.session.will_message
            payload.will_topic = self.session.will_topic
        else:
            vh.will_flag = False

        return ConnectPacket(variable_header=vh, payload=payload)

    async def mqtt_connect(self) -> int | None:
        connect_packet = self._build_connect_packet()
        await self._send_packet(connect_packet)

        if self.reader is None:
            msg = "Reader is not initialized."
            raise AMQTTError(msg)
        try:
            connack = await ConnackPacket.from_stream(self.reader)
        except NoDataError as e:
            raise ConnectionError from e
        await self.plugins_manager.fire_event(MQTTEvents.PACKET_RECEIVED, packet=connack, session=self.session)
        return connack.return_code

    def handle_write_timeout(self) -> None:
        try:
            if not self._ping_task:
                self.logger.debug("Scheduling Ping")
                self._ping_task = asyncio.create_task(self.mqtt_ping())
        except asyncio.InvalidStateError as e:
            self.logger.warning(f"Invalid state while scheduling ping task: {e!r}")
        except asyncio.CancelledError as e:
            self.logger.info(f"Ping task was cancelled: {e!r}")

    def handle_read_timeout(self) -> None:
        pass

    async def mqtt_subscribe(self, topics: list[tuple[str, int]], packet_id: int) -> list[int]:
        """Subscribe to the given topics.

        :param topics: List of tuples, e.g. [('filter', '/a/b', 'qos': 0x00)].
        :return: Return codes for the subscription.
        """
        subscribe = SubscribePacket.build(topics, packet_id)
        await self._send_packet(subscribe)

        if subscribe.variable_header is None:
            msg = f"Invalid variable header in SUBSCRIBE packet: {subscribe.variable_header}"
            raise AMQTTError(msg)

        waiter: asyncio.Future[list[int]] = asyncio.Future()
        self._subscriptions_waiter[subscribe.variable_header.packet_id] = waiter
        try:
            return_codes = await waiter
        finally:
            del self._subscriptions_waiter[subscribe.variable_header.packet_id]
        return return_codes

    async def handle_suback(self, suback: SubackPacket) -> None:
        if suback.variable_header is None:
            msg = "SUBACK packet: variable header not initialized."
            raise AMQTTError(msg)
        if suback.payload is None:
            msg = "SUBACK packet: payload not initialized."
            raise AMQTTError(msg)

        packet_id = suback.variable_header.packet_id

        waiter = self._subscriptions_waiter.get(packet_id)
        if waiter is not None:
            waiter.set_result(suback.payload.return_codes)
        else:
            self.logger.warning(f"Received SUBACK for unknown pending subscription with Id: {packet_id}")

    async def mqtt_unsubscribe(self, topics: list[str], packet_id: int) -> None:
        """Unsubscribe from the given topics.

        :param topics: List of topics ['/a/b', ...].
        """
        unsubscribe = UnsubscribePacket.build(topics, packet_id)

        if unsubscribe.variable_header is None:
            msg = "UNSUBSCRIBE packet: variable header not initialized."
            raise AMQTTError(msg)

        await self._send_packet(unsubscribe)
        waiter: asyncio.Future[Any] = asyncio.Future()
        self._unsubscriptions_waiter[unsubscribe.variable_header.packet_id] = waiter
        try:
            await waiter
        finally:
            del self._unsubscriptions_waiter[unsubscribe.variable_header.packet_id]

    async def handle_unsuback(self, unsuback: UnsubackPacket) -> None:
        if unsuback.variable_header is None:
            msg = "UNSUBACK packet: variable header not initialized."
            raise AMQTTError(msg)

        packet_id = unsuback.variable_header.packet_id
        waiter = self._unsubscriptions_waiter.get(packet_id)
        if waiter is not None:
            waiter.set_result(None)
        else:
            self.logger.warning(f"Received UNSUBACK for unknown pending unsubscription with Id: {packet_id}")

    async def mqtt_disconnect(self) -> None:
        disconnect_packet = DisconnectPacket()
        await self._send_packet(disconnect_packet)

    async def mqtt_ping(self) -> PingRespPacket:
        ping_packet = PingReqPacket()
        try:
            await self._send_packet(ping_packet)
            resp = await self._pingresp_queue.get()
        finally:
            self._ping_task = None  # Ensure the task is cleaned up
        return resp

    async def handle_pingresp(self, pingresp: PingRespPacket) -> None:
        await self._pingresp_queue.put(pingresp)

    async def handle_connection_closed(self) -> None:
        self.logger.debug("Broker closed connection")
        if self._disconnect_waiter is not None and not self._disconnect_waiter.done():
            self._disconnect_waiter.set_result(None)

    async def wait_disconnect(self) -> None:
        if self._disconnect_waiter is not None:
            await self._disconnect_waiter
