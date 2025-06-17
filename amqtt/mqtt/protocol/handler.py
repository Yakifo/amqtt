import asyncio

try:
    from asyncio import InvalidStateError, QueueFull, QueueShutDown
except ImportError:
    # Fallback for Python < 3.12
    class InvalidStateError(Exception):  #  type: ignore[no-redef]
        pass

    class QueueFull(Exception):  #  type: ignore[no-redef]  # noqa : N818
        pass

    class QueueShutDown(Exception):  #  type: ignore[no-redef]  # noqa : N818
        pass


import collections
import itertools
import logging
from typing import Generic, TypeVar, cast

from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.errors import AMQTTError, MQTTError, NoDataError, ProtocolHandlerError
from amqtt.events import MQTTEvents
from amqtt.mqtt import packet_class
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.mqtt.disconnect import DisconnectPacket
from amqtt.mqtt.packet import (
    CONNACK,
    CONNECT,
    DISCONNECT,
    PINGREQ,
    PINGRESP,
    PUBACK,
    PUBCOMP,
    PUBLISH,
    PUBREC,
    PUBREL,
    RESERVED_0,
    RESERVED_15,
    SUBACK,
    SUBSCRIBE,
    UNSUBACK,
    UNSUBSCRIBE,
    MQTTFixedHeader,
)
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.pingresp import PingRespPacket
from amqtt.mqtt.puback import PubackPacket
from amqtt.mqtt.pubcomp import PubcompPacket
from amqtt.mqtt.publish import PublishPacket
from amqtt.mqtt.pubrec import PubrecPacket
from amqtt.mqtt.pubrel import PubrelPacket
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.mqtt.unsuback import UnsubackPacket
from amqtt.mqtt.unsubscribe import UnsubscribePacket
from amqtt.plugins.manager import BaseContext, PluginManager
from amqtt.session import INCOMING, OUTGOING, ApplicationMessage, IncomingApplicationMessage, OutgoingApplicationMessage, Session

C = TypeVar("C", bound=BaseContext)

class ProtocolHandler(Generic[C]):
    """Class implementing the MQTT communication protocol using asyncio features."""

    def __init__(
        self,
        plugins_manager: PluginManager[C],
        session: Session | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.logger: logging.Logger | logging.LoggerAdapter[logging.Logger] = logging.getLogger(__name__)
        if session is not None:
            self._init_session(session)
        else:
            self.session: Session | None = None
        self.reader: ReaderAdapter | None = None
        self.writer: WriterAdapter | None = None
        self.plugins_manager: PluginManager[C] = plugins_manager

        try:
            self._loop = loop if loop is not None else asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._reader_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.TimerHandle | None = None
        self._reader_ready: asyncio.Event | None = None
        self._reader_stopped = asyncio.Event()
        self._puback_waiters: dict[int, asyncio.Future[PubackPacket]] = {}
        self._pubrec_waiters: dict[int, asyncio.Future[PubrecPacket]] = {}
        self._pubrel_waiters: dict[int, asyncio.Future[PubrelPacket]] = {}
        self._pubcomp_waiters: dict[int, asyncio.Future[PubcompPacket]] = {}
        self._write_lock = asyncio.Lock()

    def _init_session(self, session: Session) -> None:
        if not session:
            msg = "Session cannot be None"
            raise AMQTTError(msg)
        log = logging.getLogger(__name__)
        self.session = session
        self.logger = logging.LoggerAdapter(log, {"client_id": self.session.client_id})
        self.keepalive_timeout: int | None = self.session.keep_alive
        if self.keepalive_timeout <= 0:
            self.keepalive_timeout = None

    def attach(self, session: Session, reader: ReaderAdapter, writer: WriterAdapter) -> None:
        if self.session:
            msg = "Handler is already attached to a session"
            raise ProtocolHandlerError(msg)
        self._init_session(session)
        self.reader = reader
        self.writer = writer

    def detach(self) -> None:
        self.session = None
        self.reader = None
        self.writer = None

    def _is_attached(self) -> bool:
        return bool(self.session)

    async def start(self) -> None:
        if not self._is_attached():
            msg = "Handler is not attached to a stream"
            raise ProtocolHandlerError(msg)
        self._reader_ready = asyncio.Event()
        self._reader_stopped = asyncio.Event()
        self._reader_task = asyncio.create_task(self._reader_loop())
        await self._reader_ready.wait()
        if self._loop is not None and self.keepalive_timeout is not None:
            self._keepalive_task = self._loop.call_later(self.keepalive_timeout, self.handle_write_timeout)
        self.logger.debug("Handler tasks started")
        await self._retry_deliveries()
        self.logger.debug("Handler ready")

    async def stop(self) -> None:
        # Stop messages flow waiter
        self._stop_waiters()
        if self._keepalive_task:
            self._keepalive_task.cancel()
        self.logger.debug("Waiting for tasks to be stopped")
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            await self._reader_stopped.wait()
        self.logger.debug("Closing writer")
        try:
            if self.writer is not None:
                await self.writer.close()
        except asyncio.CancelledError:
            # canceling the task is the expected result
            self.logger.debug("Writer close was cancelled.")
        except TimeoutError:
            self.logger.debug("Writer close operation timed out.", exc_info=True)
        except OSError:
            self.logger.debug("Writer close failed due to I/O error.", exc_info=True)

    def _stop_waiters(self) -> None:
        self.logger.debug(f"Stopping {len(self._puback_waiters)} puback waiters")
        self.logger.debug(f"Stopping {len(self._pubcomp_waiters)} pucomp waiters")
        self.logger.debug(f"Stopping {len(self._pubrec_waiters)} purec waiters")
        self.logger.debug(f"Stopping {len(self._pubrel_waiters)} purel waiters")
        for waiter in itertools.chain(
            self._puback_waiters.values(),
            self._pubcomp_waiters.values(),
            self._pubrec_waiters.values(),
            self._pubrel_waiters.values(),
        ):
            if not isinstance(waiter, asyncio.Future):
                msg = "Waiter is not a asyncio.Future"
                raise AMQTTError(msg)
            waiter.cancel()

    async def _retry_deliveries(self) -> None:
        """Handle [MQTT-4.4.0-1] by resending PUBLISH and PUBREL messages for pending out messages."""
        self.logger.debug("Begin messages delivery retries")
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        tasks = [
            asyncio.create_task(
                asyncio.wait_for(
                    self._handle_message_flow(cast("IncomingApplicationMessage | OutgoingApplicationMessage", message)),
                    10,
                ),
            )
            for message in itertools.chain(self.session.inflight_in.values(), self.session.inflight_out.values())
        ]
        if tasks:
            done, pending = await asyncio.wait(tasks)
            self.logger.debug(f"{len(done)} messages redelivered")
            self.logger.debug(f"{len(pending)} messages not redelivered due to timeout")
        self.logger.debug("End messages delivery retries")

    async def mqtt_publish(
        self,
        topic: str,
        data: bytes | bytearray ,
        qos: int | None,
        retain: bool,
        ack_timeout: int | None = None,
    ) -> OutgoingApplicationMessage:
        """Send a MQTT publish message and manage messages flows.

        This method doesn't return until the message has been acknowledged by receiver or timeout occurs.
        :param topic: MQTT topic to publish
        :param data:  data to send on topic
        :param qos: quality of service to use for message flow. Can be QOS_0, QOS_1 or QOS_2
        :param retain: retain message flag
        :param ack_timeout: acknowledge timeout. If set, this method will return a TimeOut error if the acknowledgment
        is not completed before ack_timeout second
        :return: ApplicationMessage used during inflight operations.
        """
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        if qos in (QOS_1, QOS_2):
            packet_id = self.session.next_packet_id
            if packet_id in self.session.inflight_out:
                msg = f"A message with the same packet ID '{packet_id}' is already in flight"
                raise AMQTTError(msg)
        else:
            packet_id = None
        message: OutgoingApplicationMessage = OutgoingApplicationMessage(packet_id, topic, qos, data, retain)
        # Handle message flow
        if ack_timeout is not None and ack_timeout > 0:
            await asyncio.wait_for(self._handle_message_flow(message), ack_timeout)
        else:
            await self._handle_message_flow(message)
        return message

    async def _handle_message_flow(self, app_message: IncomingApplicationMessage | OutgoingApplicationMessage) -> None:
        """Handle protocol flow for incoming and outgoing messages.

        Depending on service level and according to MQTT spec. paragraph 4.3-Quality of Service levels and protocol flows.
        :param app_message: PublishMessage to handle
        """
        if app_message.qos not in (QOS_0, QOS_1, QOS_2):
            msg = f"Unexpected QOS value '{app_message.qos}' for message: {app_message}"
            raise AMQTTError(msg)
        if app_message.qos == QOS_0:
            await self._handle_qos0_message_flow(app_message)
        elif app_message.qos == QOS_1:
            await self._handle_qos1_message_flow(app_message)
        elif app_message.qos == QOS_2:
            await self._handle_qos2_message_flow(app_message)
        else:
            msg = f"Unexpected QOS value '{app_message.qos}'"
            raise AMQTTError(msg)

    async def _handle_qos0_message_flow(self, app_message: IncomingApplicationMessage | OutgoingApplicationMessage) -> None:
        """Handle QOS_0 application message acknowledgment.

        For incoming messages, this method stores the message.
        For outgoing messages, this methods sends PUBLISH.
        :param app_message: Application message to handle
        """
        if app_message.qos != QOS_0:
            msg = f"Expected QOS_0 message, got QOS_{app_message.qos}"
            raise ValueError(msg)
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        if app_message.direction == OUTGOING:
            packet = app_message.build_publish_packet()
            # Send PUBLISH packet
            await self._send_packet(packet)
            app_message.publish_packet = packet
        elif app_message.direction == INCOMING:
            if app_message.publish_packet is not None and app_message.publish_packet.dup_flag:
                self.logger.warning(
                    "[MQTT-3.3.1-2] DUP flag must set to 0 for QOS 0 message. Message ignored: %r",
                    app_message.publish_packet,
                )
            else:
                try:
                    self.session.delivered_message_queue.put_nowait(app_message)
                    self.logger.debug(f"Message added to delivery queue: {app_message}")
                except QueueShutDown as e:
                    self.logger.warning(f"Delivered messages queue is shut down. QOS_0 message discarded: {e}")
                except QueueFull as e:
                    self.logger.warning(f"Delivered messages queue is full. QOS_0 message discarded: {e}")

    async def _handle_qos1_message_flow(self, app_message: OutgoingApplicationMessage | IncomingApplicationMessage) -> None:
        """Handle QOS_1 application message acknowledgment.

        For incoming messages, this method stores the message and reply with PUBACK.
        For outgoing messages, this methods sends PUBLISH and waits for the corresponding PUBACK.
        :param app_message: Application message to handle
        """
        if app_message.qos != QOS_1:
            msg = f"Expected QOS_1 message, got QOS_{app_message.qos}"
            raise ValueError(msg)
        if app_message.packet_id is None:
            msg = "Packet ID is not set"
            raise ValueError(msg)
        if app_message.puback_packet:
            msg = f"Message '{app_message.packet_id}' has already been acknowledged"
            raise AMQTTError(msg)
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)

        if app_message.direction == OUTGOING:
            if app_message.packet_id not in self.session.inflight_out and isinstance(app_message, OutgoingApplicationMessage):
                # Store message in session
                self.session.inflight_out[app_message.packet_id] = app_message
            if app_message.publish_packet is not None:
                # A Publish packet has already been sent, this is a retry
                publish_packet = app_message.build_publish_packet(dup=True)
            else:
                publish_packet = app_message.build_publish_packet()
            # Send PUBLISH packet
            await self._send_packet(publish_packet)
            app_message.publish_packet = publish_packet
            # Wait for puback
            waiter: asyncio.Future[PubackPacket] = asyncio.Future()
            self._puback_waiters[app_message.packet_id] = waiter
            try:
                app_message.puback_packet = await asyncio.wait_for(waiter, timeout=5)
            except TimeoutError:
                msg = f"Timeout waiting for PUBACK for packet ID {app_message.packet_id}"
                self.logger.warning(msg)
                raise TimeoutError(msg) from None
            finally:
                self._puback_waiters.pop(app_message.packet_id, None)
                # Discard inflight message
                self.session.inflight_out.pop(app_message.packet_id, None)
        elif app_message.direction == INCOMING:
            # Initiate delivery
            self.logger.debug("Add message to delivery")
            await self.session.delivered_message_queue.put(app_message)
            # Send PUBACK
            puback = PubackPacket.build(app_message.packet_id)
            await self._send_packet(puback)
            app_message.puback_packet = puback

    async def _handle_qos2_message_flow(self, app_message: OutgoingApplicationMessage | IncomingApplicationMessage) -> None:
        """Handle QOS_2 application message acknowledgment.

        For incoming messages, this method stores the message, sends PUBREC, waits for PUBREL, initiate delivery
        and send PUBCOMP.
        For outgoing messages, this methods sends PUBLISH, waits for PUBREC, discards messages and wait for PUBCOMP.
        :param app_message: Application message to handle
        """
        if app_message.qos != QOS_2:
            msg = f"Expected QOS_2 message, got QOS_{app_message.qos}"
            raise ValueError(msg)
        if app_message.packet_id is None:
            msg = "Packet ID is not set"
            raise ValueError(msg)
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)

        if app_message.direction == OUTGOING:
            if app_message.pubrel_packet and app_message.pubcomp_packet:
                msg = f"Message '{app_message.packet_id}' has already been acknowledged"
                raise AMQTTError(msg)

            if not app_message.pubrel_packet:
                # Store message
                publish_packet: PublishPacket
                if app_message.publish_packet is not None:
                    # This is a retry flow, no need to store just check the message exists in session
                    if app_message.packet_id not in self.session.inflight_out:
                        msg = f"Unknown inflight message '{app_message.packet_id}' in session"
                        raise AMQTTError(msg)
                    publish_packet = app_message.build_publish_packet(dup=True)
                elif isinstance(app_message, OutgoingApplicationMessage):
                    # Store message in session
                    self.session.inflight_out[app_message.packet_id] = app_message
                    publish_packet = app_message.build_publish_packet()
                else:
                    self.logger.debug("Message can not be stored, to be checked!")
                # Send PUBLISH packet
                await self._send_packet(publish_packet)
                app_message.publish_packet = publish_packet
                # Wait PUBREC
                if app_message.packet_id in self._pubrec_waiters:
                    # PUBREC waiter already exists for this packet ID
                    message = f"Can't add PUBREC waiter, a waiter already exists for message Id '{app_message.packet_id}'"
                    self.logger.warning(message)
                    raise AMQTTError(message)
                waiter_pub_rec: asyncio.Future[PubrecPacket] = asyncio.Future()
                self._pubrec_waiters[app_message.packet_id] = waiter_pub_rec
                try:
                    app_message.pubrec_packet = await waiter_pub_rec
                finally:
                    self._pubrec_waiters.pop(app_message.packet_id, None)
                    self.session.inflight_out.pop(app_message.packet_id, None)

            if not app_message.pubcomp_packet:
                # Send pubrel
                app_message.pubrel_packet = PubrelPacket.build(app_message.packet_id)
                await self._send_packet(app_message.pubrel_packet)
                # Wait for PUBCOMP
                waiter_pub_comp: asyncio.Future[PubcompPacket] = asyncio.Future()
                self._pubcomp_waiters[app_message.packet_id] = waiter_pub_comp
                try:
                    app_message.pubcomp_packet = await waiter_pub_comp
                finally:
                    self._pubcomp_waiters.pop(app_message.packet_id, None)
                    self.session.inflight_out.pop(app_message.packet_id, None)
        elif app_message.direction == INCOMING and isinstance(app_message, IncomingApplicationMessage):
            self.session.inflight_in[app_message.packet_id] = app_message
            # Send pubrec
            pubrec_packet = PubrecPacket.build(app_message.packet_id)
            await self._send_packet(pubrec_packet)
            app_message.pubrec_packet = pubrec_packet
            # Wait PUBREL
            if app_message.packet_id in self._pubrel_waiters and not self._pubrel_waiters[app_message.packet_id].done():
                # PUBREL waiter already exists for this packet ID
                message = f"A waiter already exists for message Id '{app_message.packet_id}', canceling it"
                self.logger.warning(message)
                self._pubrel_waiters[app_message.packet_id].cancel()
            try:
                waiter_pub_rel: asyncio.Future[PubrelPacket] = asyncio.Future()
                self._pubrel_waiters[app_message.packet_id] = waiter_pub_rel
                await waiter_pub_rel
                del self._pubrel_waiters[app_message.packet_id]
                app_message.pubrel_packet = waiter_pub_rel.result()
                # Initiate delivery and discard message
                await self.session.delivered_message_queue.put(app_message)
                del self.session.inflight_in[app_message.packet_id]
                # Send pubcomp
                pubcomp_packet = PubcompPacket.build(app_message.packet_id)
                await self._send_packet(pubcomp_packet)
                app_message.pubcomp_packet = pubcomp_packet
            except asyncio.CancelledError:
                self.logger.debug("Message flow cancelled")
        else:
            self.logger.debug("Unknown direction!")

    async def _reader_loop(self) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        if not self._reader_ready:
            msg = "Reader ready is not initialized."
            raise ProtocolHandlerError(msg)

        self.logger.debug(f"{self.session.client_id} Starting reader coro")
        running_tasks: collections.deque[asyncio.Task[None]] = collections.deque()
        keepalive_timeout: int | None = self.session.keep_alive
        if keepalive_timeout is not None and keepalive_timeout <= 0:
            keepalive_timeout = None
        while True:
            try:
                self._reader_ready.set()
                while running_tasks and running_tasks[0].done():
                    running_tasks.popleft()
                if len(running_tasks) > 1:
                    self.logger.debug(f"Handler running tasks: {len(running_tasks)}")
                if self.reader is None:
                    self.logger.warning("Reader is not initialized!")
                    break
                fixed_header = await asyncio.wait_for(MQTTFixedHeader.from_stream(self.reader), timeout=keepalive_timeout)
                if not fixed_header:
                    self.logger.debug(f"{self.session.client_id} No more data (EOF received), stopping reader coro")
                    break
                if fixed_header.packet_type in (RESERVED_0, RESERVED_15):
                    self.logger.warning(
                        f"{self.session.client_id} Received reserved packet, which is forbidden: closing connection",
                    )
                    await self.handle_connection_closed()
                    continue

                cls = packet_class(fixed_header)
                packet = await cls.from_stream(self.reader, fixed_header=fixed_header)
                await self.plugins_manager.fire_event(MQTTEvents.PACKET_RECEIVED, packet=packet, session=self.session)
                if packet.fixed_header is None or packet.fixed_header.packet_type not in (
                    CONNACK,
                    SUBSCRIBE,
                    UNSUBSCRIBE,
                    SUBACK,
                    UNSUBACK,
                    PUBACK,
                    PUBREC,
                    PUBREL,
                    PUBCOMP,
                    PINGREQ,
                    PINGRESP,
                    PUBLISH,
                    DISCONNECT,
                    CONNECT,
                ):
                    self.logger.warning(f"{self.session.client_id} Unhandled packet type: {packet.fixed_header.packet_type}")
                    continue

                task: asyncio.Task[None] | None = None
                if packet.fixed_header.packet_type == CONNACK and isinstance(packet, ConnackPacket):
                    task = asyncio.create_task(self.handle_connack(packet))
                elif packet.fixed_header.packet_type == SUBSCRIBE and isinstance(packet, SubscribePacket):
                    task = asyncio.create_task(self.handle_subscribe(packet))
                elif packet.fixed_header.packet_type == UNSUBSCRIBE and isinstance(packet, UnsubscribePacket):
                    task = asyncio.create_task(self.handle_unsubscribe(packet))
                elif packet.fixed_header.packet_type == SUBACK and isinstance(packet, SubackPacket):
                    task = asyncio.create_task(self.handle_suback(packet))
                elif packet.fixed_header.packet_type == UNSUBACK and isinstance(packet, UnsubackPacket):
                    task = asyncio.create_task(self.handle_unsuback(packet))
                elif packet.fixed_header.packet_type == PUBACK and isinstance(packet, PubackPacket):
                    task = asyncio.create_task(self.handle_puback(packet))
                elif packet.fixed_header.packet_type == PUBREC and isinstance(packet, PubrecPacket):
                    task = asyncio.create_task(self.handle_pubrec(packet))
                elif packet.fixed_header.packet_type == PUBREL and isinstance(packet, PubrelPacket):
                    task = asyncio.create_task(self.handle_pubrel(packet))
                elif packet.fixed_header.packet_type == PUBCOMP and isinstance(packet, PubcompPacket):
                    task = asyncio.create_task(self.handle_pubcomp(packet))
                elif packet.fixed_header.packet_type == PINGREQ and isinstance(packet, PingReqPacket):
                    task = asyncio.create_task(self.handle_pingreq(packet))
                elif packet.fixed_header.packet_type == PINGRESP and isinstance(packet, PingRespPacket):
                    task = asyncio.create_task(self.handle_pingresp(packet))
                elif packet.fixed_header.packet_type == PUBLISH and isinstance(packet, PublishPacket):
                    task = asyncio.create_task(self.handle_publish(packet))
                elif packet.fixed_header.packet_type == DISCONNECT and isinstance(packet, DisconnectPacket):
                    task = asyncio.create_task(self.handle_disconnect(packet))
                elif packet.fixed_header.packet_type == CONNECT and isinstance(packet, ConnectPacket):
                    # TODO: why is this not like all other inside create_task?
                    await self.handle_connect(packet)  # task = asyncio.create_task(self.handle_connect(packet))
                if task:
                    running_tasks.append(task)
            except MQTTError:
                self.logger.debug("Message discarded")
            except asyncio.CancelledError:
                self.logger.debug("Task cancelled, reader loop ending")
                break
            except TimeoutError:
                self.logger.debug(f"{self.session.client_id} Input stream read timeout")
                self.handle_read_timeout()
            except NoDataError:
                self.logger.debug(f"{self.session.client_id} No data available")
            except Exception as e:  # noqa: BLE001
                self.logger.warning(f"{type(self).__name__} Unhandled exception in reader coro: {e!r}")
                break
        while running_tasks:
            running_tasks.popleft().cancel()
        await self.handle_connection_closed()
        self._reader_stopped.set()
        self.logger.debug("Reader coro stopped")
        await self.stop()

    async def _send_packet(
        self,
        packet: PublishPacket
        | PubackPacket
        | ConnackPacket
        | SubackPacket
        | ConnectPacket
        | SubscribePacket
        | UnsubscribePacket
        | DisconnectPacket
        | PingReqPacket
        | PubrelPacket
        | PubrecPacket
        | PubcompPacket
        | PingRespPacket
        | UnsubackPacket,
    ) -> None:
        try:
            if self.writer:
                async with self._write_lock:
                    await packet.to_stream(self.writer)
            if self._keepalive_task:
                self._keepalive_task.cancel()
                if self.keepalive_timeout is not None:
                    self._keepalive_task = self._loop.call_later(self.keepalive_timeout, self.handle_write_timeout)
            await self.plugins_manager.fire_event(MQTTEvents.PACKET_SENT, packet=packet, session=self.session)
        except (ConnectionResetError, BrokenPipeError):
            await self.handle_connection_closed()
        except asyncio.CancelledError as e:
            msg = "Packet handling was cancelled"
            raise ProtocolHandlerError(msg) from e
        except Exception as e:
            self.logger.warning(f"Unhandled exception: {e}")
            raise

    async def mqtt_deliver_next_message(self) -> ApplicationMessage | None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)

        if not self._is_attached():
            return None
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"{self.session.delivered_message_queue.qsize()} message(s) available for delivery")
        message: ApplicationMessage | None = None
        try:
            message = await self.session.delivered_message_queue.get()
        except (asyncio.CancelledError, RuntimeError):
            message = None
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Delivering message {message}")
        return message

    def handle_write_timeout(self) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} write timeout unhandled")

    def handle_read_timeout(self) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} read timeout unhandled")

    async def handle_connack(self, connack: ConnackPacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} CONNACK unhandled")

    async def handle_connect(self, connect: ConnectPacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} CONNECT unhandled")

    async def handle_subscribe(self, subscribe: SubscribePacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} SUBSCRIBE unhandled")

    async def handle_unsubscribe(self, unsubscribe: UnsubscribePacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} UNSUBSCRIBE unhandled")

    async def handle_suback(self, suback: SubackPacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} SUBACK unhandled")

    async def handle_unsuback(self, unsuback: UnsubackPacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} UNSUBACK unhandled")

    async def handle_pingresp(self, pingresp: PingRespPacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} PINGRESP unhandled")

    async def handle_pingreq(self, pingreq: PingReqPacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} PINGREQ unhandled")

    async def handle_disconnect(self, disconnect: DisconnectPacket) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} DISCONNECT unhandled")

    async def handle_connection_closed(self) -> None:
        if self.session is None:
            msg = "Session is not initialized."
            raise AMQTTError(msg)
        self.logger.debug(f"{self.session.client_id} Connection closed unhandled")

    async def handle_puback(self, puback: PubackPacket) -> None:
        if puback.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        packet_id = puback.variable_header.packet_id
        try:
            waiter = self._puback_waiters[packet_id]
            waiter.set_result(puback)
        except KeyError:
            self.logger.warning(f"Received PUBACK for unknown pending message Id: '{packet_id}'")
        except InvalidStateError:
            self.logger.warning(f"PUBACK waiter with Id '{packet_id}' already done")

    async def handle_pubrec(self, pubrec: PubrecPacket) -> None:
        packet_id = pubrec.packet_id
        try:
            waiter = self._pubrec_waiters[packet_id]
            waiter.set_result(pubrec)
        except KeyError:
            self.logger.warning(f"Received PUBREC for unknown pending message with Id: {packet_id}")
        except InvalidStateError:
            self.logger.warning(f"PUBREC waiter with Id '{packet_id}' already done")

    async def handle_pubcomp(self, pubcomp: PubcompPacket) -> None:
        packet_id = pubcomp.packet_id
        try:
            waiter = self._pubcomp_waiters[packet_id]
            waiter.set_result(pubcomp)
        except KeyError:
            self.logger.warning(f"Received PUBCOMP for unknown pending message with Id: {packet_id}")
        except InvalidStateError:
            self.logger.warning(f"PUBCOMP waiter with Id '{packet_id}' already done")

    async def handle_pubrel(self, pubrel: PubrelPacket) -> None:
        packet_id = pubrel.packet_id
        try:
            waiter = self._pubrel_waiters[packet_id]
            waiter.set_result(pubrel)
        except KeyError:
            self.logger.warning(f"Received PUBREL for unknown pending message with Id: {packet_id}")
        except InvalidStateError:
            self.logger.warning(f"PUBREL waiter with Id '{packet_id}' already done")

    async def handle_publish(self, publish_packet: PublishPacket) -> None:
        packet_id = publish_packet.variable_header.packet_id if publish_packet.variable_header else None
        qos = publish_packet.qos
        if publish_packet.topic_name is None or publish_packet.data is None:
            return
        incoming_message = IncomingApplicationMessage(
            packet_id,
            publish_packet.topic_name,
            qos,
            publish_packet.data,
            publish_packet.retain_flag,
        )
        incoming_message.publish_packet = publish_packet
        await self._handle_message_flow(incoming_message)
        self.logger.debug(f"Message queue size: {self.session.delivered_message_queue.qsize() if self.session else None}")
