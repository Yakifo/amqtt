# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import logging
import collections
import itertools

import asyncio
from asyncio import InvalidStateError

from amqtt.mqtt import packet_class
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket
from amqtt.mqtt.packet import (
    RESERVED_0,
    CONNECT,
    CONNACK,
    PUBLISH,
    PUBACK,
    PUBREC,
    PUBREL,
    PUBCOMP,
    SUBSCRIBE,
    SUBACK,
    UNSUBSCRIBE,
    UNSUBACK,
    PINGREQ,
    PINGRESP,
    DISCONNECT,
    RESERVED_15,
    MQTTFixedHeader,
)
from amqtt.mqtt.pingresp import PingRespPacket
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.publish import PublishPacket
from amqtt.mqtt.pubrel import PubrelPacket
from amqtt.mqtt.puback import PubackPacket
from amqtt.mqtt.pubrec import PubrecPacket
from amqtt.mqtt.pubcomp import PubcompPacket
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.mqtt.unsubscribe import UnsubscribePacket
from amqtt.mqtt.unsuback import UnsubackPacket
from amqtt.mqtt.disconnect import DisconnectPacket
from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.session import (
    Session,
    OutgoingApplicationMessage,
    IncomingApplicationMessage,
    INCOMING,
    OUTGOING,
)
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
from amqtt.plugins.manager import PluginManager
from amqtt.errors import AMQTTException, MQTTException, NoDataException


EVENT_MQTT_PACKET_SENT = "mqtt_packet_sent"
EVENT_MQTT_PACKET_RECEIVED = "mqtt_packet_received"


class ProtocolHandlerException(Exception):
    pass


class ProtocolHandler:
    """
    Class implementing the MQTT communication protocol using asyncio features
    """

    def __init__(
        self, plugins_manager: PluginManager, session: Session = None, loop=None
    ):
        self.logger = logging.getLogger(__name__)
        if session:
            self._init_session(session)
        else:
            self.session = None
        self.reader = None
        self.writer = None
        self.plugins_manager = plugins_manager

        if loop is None:
            self._loop = asyncio.get_event_loop()
        else:
            self._loop = loop
        self._reader_task = None
        self._keepalive_task = None
        self._reader_ready = None
        self._reader_stopped = asyncio.Event()

        self._puback_waiters = dict()
        self._pubrec_waiters = dict()
        self._pubrel_waiters = dict()
        self._pubcomp_waiters = dict()

        self._write_lock = asyncio.Lock()

    def _init_session(self, session: Session):
        assert session
        log = logging.getLogger(__name__)
        self.session = session
        self.logger = logging.LoggerAdapter(log, {"client_id": self.session.client_id})
        self.keepalive_timeout = self.session.keep_alive
        if self.keepalive_timeout <= 0:
            self.keepalive_timeout = None

    def attach(self, session, reader: ReaderAdapter, writer: WriterAdapter):
        if self.session:
            raise ProtocolHandlerException("Handler is already attached to a session")
        self._init_session(session)
        self.reader = reader
        self.writer = writer

    def detach(self):
        self.session = None
        self.reader = None
        self.writer = None

    def _is_attached(self):
        if self.session:
            return True
        else:
            return False

    async def start(self):
        if not self._is_attached():
            raise ProtocolHandlerException("Handler is not attached to a stream")
        self._reader_ready = asyncio.Event()
        self._reader_task = asyncio.Task(self._reader_loop())
        await self._reader_ready.wait()
        if self.keepalive_timeout:
            self._keepalive_task = self._loop.call_later(
                self.keepalive_timeout, self.handle_write_timeout
            )

        self.logger.debug("Handler tasks started")
        await self._retry_deliveries()
        self.logger.debug("Handler ready")

    async def stop(self):
        # Stop messages flow waiter
        self._stop_waiters()
        if self._keepalive_task:
            self._keepalive_task.cancel()
        self.logger.debug("waiting for tasks to be stopped")
        if not self._reader_task.done():
            self._reader_task.cancel()
            await self._reader_stopped.wait()
        self.logger.debug("closing writer")
        try:
            await self.writer.close()
        except Exception as e:
            self.logger.debug("Handler writer close failed: %s" % e)

    def _stop_waiters(self):
        self.logger.debug("Stopping %d puback waiters" % len(self._puback_waiters))
        self.logger.debug("Stopping %d pucomp waiters" % len(self._pubcomp_waiters))
        self.logger.debug("Stopping %d purec waiters" % len(self._pubrec_waiters))
        self.logger.debug("Stopping %d purel waiters" % len(self._pubrel_waiters))
        for waiter in itertools.chain(
            self._puback_waiters.values(),
            self._pubcomp_waiters.values(),
            self._pubrec_waiters.values(),
            self._pubrel_waiters.values(),
        ):
            waiter.cancel()

    async def _retry_deliveries(self):
        """
        Handle [MQTT-4.4.0-1] by resending PUBLISH and PUBREL messages for pending out messages
        :return:
        """
        self.logger.debug("Begin messages delivery retries")
        tasks = []
        for message in itertools.chain(
            self.session.inflight_in.values(), self.session.inflight_out.values()
        ):
            tasks.append(
                asyncio.create_task(
                    asyncio.wait_for(self._handle_message_flow(message), 10)
                )
            )
        if tasks:
            done, pending = await asyncio.wait(tasks)
            self.logger.debug("%d messages redelivered" % len(done))
            self.logger.debug(
                "%d messages not redelivered due to timeout" % len(pending)
            )
        self.logger.debug("End messages delivery retries")

    async def mqtt_publish(self, topic, data, qos, retain, ack_timeout=None):
        """
        Sends a MQTT publish message and manages messages flows.
        This methods doesn't return until the message has been acknowledged by receiver or timeout occur
        :param topic: MQTT topic to publish
        :param data:  data to send on topic
        :param qos: quality of service to use for message flow. Can be QOS_0, QOS_1 or QOS_2
        :param retain: retain message flag
        :param ack_timeout: acknowledge timeout. If set, this method will return a TimeOut error if the acknowledgment
        is not completed before ack_timeout second
        :return: ApplicationMessage used during inflight operations
        """
        if qos in (QOS_1, QOS_2):
            packet_id = self.session.next_packet_id
            if packet_id in self.session.inflight_out:
                raise AMQTTException(
                    "A message with the same packet ID '%d' is already in flight"
                    % packet_id
                )
        else:
            packet_id = None

        message = OutgoingApplicationMessage(packet_id, topic, qos, data, retain)
        # Handle message flow
        if ack_timeout is not None and ack_timeout > 0:
            await asyncio.wait_for(self._handle_message_flow(message), ack_timeout)
        else:
            await self._handle_message_flow(message)

        return message

    async def _handle_message_flow(self, app_message):
        """
        Handle protocol flow for incoming and outgoing messages, depending on service level and according to MQTT
        spec. paragraph 4.3-Quality of Service levels and protocol flows
        :param app_message: PublishMessage to handle
        :return: nothing.
        """
        if app_message.qos == QOS_0:
            await self._handle_qos0_message_flow(app_message)
        elif app_message.qos == QOS_1:
            await self._handle_qos1_message_flow(app_message)
        elif app_message.qos == QOS_2:
            await self._handle_qos2_message_flow(app_message)
        else:
            raise AMQTTException("Unexcepted QOS value '%d" % str(app_message.qos))

    async def _handle_qos0_message_flow(self, app_message):
        """
        Handle QOS_0 application message acknowledgment
        For incoming messages, this method stores the message
        For outgoing messages, this methods sends PUBLISH
        :param app_message:
        :return:
        """
        assert app_message.qos == QOS_0
        if app_message.direction == OUTGOING:
            packet = app_message.build_publish_packet()
            # Send PUBLISH packet
            await self._send_packet(packet)
            app_message.publish_packet = packet
        elif app_message.direction == INCOMING:
            if app_message.publish_packet.dup_flag:
                self.logger.warning(
                    "[MQTT-3.3.1-2] DUP flag must set to 0 for QOS 0 message. Message ignored: %s"
                    % repr(app_message.publish_packet)
                )
            else:
                try:
                    self.session.delivered_message_queue.put_nowait(app_message)
                except:
                    self.logger.warning(
                        "delivered messages queue full. QOS_0 message discarded"
                    )

    async def _handle_qos1_message_flow(self, app_message):
        """
        Handle QOS_1 application message acknowledgment
        For incoming messages, this method stores the message and reply with PUBACK
        For outgoing messages, this methods sends PUBLISH and waits for the corresponding PUBACK
        :param app_message:
        :return:
        """
        assert app_message.qos == QOS_1
        if app_message.puback_packet:
            raise AMQTTException(
                "Message '%d' has already been acknowledged" % app_message.packet_id
            )
        if app_message.direction == OUTGOING:
            if app_message.packet_id not in self.session.inflight_out:
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
            waiter = asyncio.Future()
            self._puback_waiters[app_message.packet_id] = waiter
            try:
                await waiter
                app_message.puback_packet = waiter.result()
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

    async def _handle_qos2_message_flow(self, app_message):
        """
        Handle QOS_2 application message acknowledgment
        For incoming messages, this method stores the message, sends PUBREC, waits for PUBREL, initiate delivery
        and send PUBCOMP
        For outgoing messages, this methods sends PUBLISH, waits for PUBREC, discards messages and wait for PUBCOMP
        :param app_message:
        :return:
        """
        assert app_message.qos == QOS_2
        if app_message.direction == OUTGOING:
            if app_message.pubrel_packet and app_message.pubcomp_packet:
                raise AMQTTException(
                    "Message '%d' has already been acknowledged" % app_message.packet_id
                )
            if not app_message.pubrel_packet:
                # Store message
                if app_message.publish_packet is not None:
                    # This is a retry flow, no need to store just check the message exists in session
                    if app_message.packet_id not in self.session.inflight_out:
                        raise AMQTTException(
                            "Unknown inflight message '%d' in session"
                            % app_message.packet_id
                        )
                    publish_packet = app_message.build_publish_packet(dup=True)
                else:
                    # Store message in session
                    self.session.inflight_out[app_message.packet_id] = app_message
                    publish_packet = app_message.build_publish_packet()
                # Send PUBLISH packet
                await self._send_packet(publish_packet)
                app_message.publish_packet = publish_packet
                # Wait PUBREC
                if app_message.packet_id in self._pubrec_waiters:
                    # PUBREC waiter already exists for this packet ID
                    message = (
                        "Can't add PUBREC waiter, a waiter already exists for message Id '%s'"
                        % app_message.packet_id
                    )
                    self.logger.warning(message)
                    raise AMQTTException(message)
                waiter = asyncio.Future()
                self._pubrec_waiters[app_message.packet_id] = waiter
                try:
                    await waiter
                    app_message.pubrec_packet = waiter.result()
                finally:
                    self._pubrec_waiters.pop(app_message.packet_id, None)
                    self.session.inflight_out.pop(app_message.packet_id, None)
            if not app_message.pubcomp_packet:
                # Send pubrel
                app_message.pubrel_packet = PubrelPacket.build(app_message.packet_id)
                await self._send_packet(app_message.pubrel_packet)
                # Wait for PUBCOMP
                waiter = asyncio.Future()
                self._pubcomp_waiters[app_message.packet_id] = waiter
                try:
                    await waiter
                    app_message.pubcomp_packet = waiter.result()
                finally:
                    self._pubcomp_waiters.pop(app_message.packet_id, None)
                    self.session.inflight_out.pop(app_message.packet_id, None)
        elif app_message.direction == INCOMING:
            self.session.inflight_in[app_message.packet_id] = app_message
            # Send pubrec
            pubrec_packet = PubrecPacket.build(app_message.packet_id)
            await self._send_packet(pubrec_packet)
            app_message.pubrec_packet = pubrec_packet
            # Wait PUBREL
            if (
                app_message.packet_id in self._pubrel_waiters
                and not self._pubrel_waiters[app_message.packet_id].done()
            ):
                # PUBREL waiter already exists for this packet ID
                message = (
                    "A waiter already exists for message Id '%s', canceling it"
                    % app_message.packet_id
                )
                self.logger.warning(message)
                self._pubrel_waiters[app_message.packet_id].cancel()
            try:
                waiter = asyncio.Future()
                self._pubrel_waiters[app_message.packet_id] = waiter
                await waiter
                del self._pubrel_waiters[app_message.packet_id]
                app_message.pubrel_packet = waiter.result()
                # Initiate delivery and discard message
                await self.session.delivered_message_queue.put(app_message)
                del self.session.inflight_in[app_message.packet_id]
                # Send pubcomp
                pubcomp_packet = PubcompPacket.build(app_message.packet_id)
                await self._send_packet(pubcomp_packet)
                app_message.pubcomp_packet = pubcomp_packet
            except asyncio.CancelledError:
                self.logger.debug("Message flow cancelled")

    async def _reader_loop(self):
        self.logger.debug("%s Starting reader coro" % self.session.client_id)
        running_tasks = collections.deque()
        keepalive_timeout = self.session.keep_alive
        if keepalive_timeout <= 0:
            keepalive_timeout = None
        while True:
            try:
                self._reader_ready.set()
                while running_tasks and running_tasks[0].done():
                    running_tasks.popleft()
                if len(running_tasks) > 1:
                    self.logger.debug("handler running tasks: %d" % len(running_tasks))

                fixed_header = await asyncio.wait_for(
                    MQTTFixedHeader.from_stream(self.reader),
                    keepalive_timeout,
                )
                if fixed_header:
                    if (
                        fixed_header.packet_type == RESERVED_0
                        or fixed_header.packet_type == RESERVED_15
                    ):
                        self.logger.warning(
                            "%s Received reserved packet, which is forbidden: closing connection"
                            % (self.session.client_id)
                        )
                        await self.handle_connection_closed()
                    else:
                        cls = packet_class(fixed_header)
                        packet = await cls.from_stream(
                            self.reader, fixed_header=fixed_header
                        )
                        await self.plugins_manager.fire_event(
                            EVENT_MQTT_PACKET_RECEIVED,
                            packet=packet,
                            session=self.session,
                        )
                        task = None
                        if packet.fixed_header.packet_type == CONNACK:
                            task = asyncio.ensure_future(self.handle_connack(packet))
                        elif packet.fixed_header.packet_type == SUBSCRIBE:
                            task = asyncio.ensure_future(self.handle_subscribe(packet))
                        elif packet.fixed_header.packet_type == UNSUBSCRIBE:
                            task = asyncio.ensure_future(
                                self.handle_unsubscribe(packet)
                            )
                        elif packet.fixed_header.packet_type == SUBACK:
                            task = asyncio.ensure_future(self.handle_suback(packet))
                        elif packet.fixed_header.packet_type == UNSUBACK:
                            task = asyncio.ensure_future(self.handle_unsuback(packet))
                        elif packet.fixed_header.packet_type == PUBACK:
                            task = asyncio.ensure_future(self.handle_puback(packet))
                        elif packet.fixed_header.packet_type == PUBREC:
                            task = asyncio.ensure_future(self.handle_pubrec(packet))
                        elif packet.fixed_header.packet_type == PUBREL:
                            task = asyncio.ensure_future(self.handle_pubrel(packet))
                        elif packet.fixed_header.packet_type == PUBCOMP:
                            task = asyncio.ensure_future(self.handle_pubcomp(packet))
                        elif packet.fixed_header.packet_type == PINGREQ:
                            task = asyncio.ensure_future(self.handle_pingreq(packet))
                        elif packet.fixed_header.packet_type == PINGRESP:
                            task = asyncio.ensure_future(self.handle_pingresp(packet))
                        elif packet.fixed_header.packet_type == PUBLISH:
                            task = asyncio.ensure_future(self.handle_publish(packet))
                        elif packet.fixed_header.packet_type == DISCONNECT:
                            task = asyncio.ensure_future(self.handle_disconnect(packet))
                        elif packet.fixed_header.packet_type == CONNECT:
                            self.handle_connect(packet)
                        else:
                            self.logger.warning(
                                "%s Unhandled packet type: %s"
                                % (
                                    self.session.client_id,
                                    packet.fixed_header.packet_type,
                                )
                            )
                        if task:
                            running_tasks.append(task)
                else:
                    self.logger.debug(
                        "%s No more data (EOF received), stopping reader coro"
                        % self.session.client_id
                    )
                    break
            except MQTTException:
                self.logger.debug("Message discarded")
            except asyncio.CancelledError:
                self.logger.debug("Task cancelled, reader loop ending")
                break
            except asyncio.TimeoutError:
                self.logger.debug(
                    "%s Input stream read timeout" % self.session.client_id
                )
                self.handle_read_timeout()
            except NoDataException:
                self.logger.debug("%s No data available" % self.session.client_id)
            except Exception as e:
                self.logger.warning(
                    "%s Unhandled exception in reader coro: %r"
                    % (type(self).__name__, e)
                )
                break
        while running_tasks:
            running_tasks.popleft().cancel()
        await self.handle_connection_closed()
        self._reader_stopped.set()
        self.logger.debug("Reader coro stopped")
        await self.stop()

    async def _send_packet(self, packet):
        try:
            async with self._write_lock:
                await packet.to_stream(self.writer)
            if self._keepalive_task:
                self._keepalive_task.cancel()
                self._keepalive_task = self._loop.call_later(
                    self.keepalive_timeout, self.handle_write_timeout
                )

            await self.plugins_manager.fire_event(
                EVENT_MQTT_PACKET_SENT, packet=packet, session=self.session
            )
        except (ConnectionResetError, BrokenPipeError):
            await self.handle_connection_closed()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.warning("Unhandled exception: %s" % e)
            raise

    async def mqtt_deliver_next_message(self):
        if not self._is_attached():
            return None
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "%d message(s) available for delivery"
                % self.session.delivered_message_queue.qsize()
            )
        try:
            message = await self.session.delivered_message_queue.get()
        except asyncio.CancelledError:
            message = None
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Delivering message %s" % message)
        return message

    def handle_write_timeout(self):
        self.logger.debug("%s write timeout unhandled" % self.session.client_id)

    def handle_read_timeout(self):
        self.logger.debug("%s read timeout unhandled" % self.session.client_id)

    async def handle_connack(self, connack: ConnackPacket):
        self.logger.debug("%s CONNACK unhandled" % self.session.client_id)

    async def handle_connect(self, connect: ConnectPacket):
        self.logger.debug("%s CONNECT unhandled" % self.session.client_id)

    async def handle_subscribe(self, subscribe: SubscribePacket):
        self.logger.debug("%s SUBSCRIBE unhandled" % self.session.client_id)

    async def handle_unsubscribe(self, subscribe: UnsubscribePacket):
        self.logger.debug("%s UNSUBSCRIBE unhandled" % self.session.client_id)

    async def handle_suback(self, suback: SubackPacket):
        self.logger.debug("%s SUBACK unhandled" % self.session.client_id)

    async def handle_unsuback(self, unsuback: UnsubackPacket):
        self.logger.debug("%s UNSUBACK unhandled" % self.session.client_id)

    async def handle_pingresp(self, pingresp: PingRespPacket):
        self.logger.debug("%s PINGRESP unhandled" % self.session.client_id)

    async def handle_pingreq(self, pingreq: PingReqPacket):
        self.logger.debug("%s PINGREQ unhandled" % self.session.client_id)

    async def handle_disconnect(self, disconnect: DisconnectPacket):
        self.logger.debug("%s DISCONNECT unhandled" % self.session.client_id)

    async def handle_connection_closed(self):
        self.logger.debug("%s Connection closed unhandled" % self.session.client_id)

    async def handle_puback(self, puback: PubackPacket):
        packet_id = puback.variable_header.packet_id
        try:
            waiter = self._puback_waiters[packet_id]
            waiter.set_result(puback)
        except KeyError:
            self.logger.warning(
                "Received PUBACK for unknown pending message Id: '%d'" % packet_id
            )
        except InvalidStateError:
            self.logger.warning("PUBACK waiter with Id '%d' already done" % packet_id)

    async def handle_pubrec(self, pubrec: PubrecPacket):
        packet_id = pubrec.packet_id
        try:
            waiter = self._pubrec_waiters[packet_id]
            waiter.set_result(pubrec)
        except KeyError:
            self.logger.warning(
                "Received PUBREC for unknown pending message with Id: %d" % packet_id
            )
        except InvalidStateError:
            self.logger.warning("PUBREC waiter with Id '%d' already done" % packet_id)

    async def handle_pubcomp(self, pubcomp: PubcompPacket):
        packet_id = pubcomp.packet_id
        try:
            waiter = self._pubcomp_waiters[packet_id]
            waiter.set_result(pubcomp)
        except KeyError:
            self.logger.warning(
                "Received PUBCOMP for unknown pending message with Id: %d" % packet_id
            )
        except InvalidStateError:
            self.logger.warning("PUBCOMP waiter with Id '%d' already done" % packet_id)

    async def handle_pubrel(self, pubrel: PubrelPacket):
        packet_id = pubrel.packet_id
        try:
            waiter = self._pubrel_waiters[packet_id]
            waiter.set_result(pubrel)
        except KeyError:
            self.logger.warning(
                "Received PUBREL for unknown pending message with Id: %d" % packet_id
            )
        except InvalidStateError:
            self.logger.warning("PUBREL waiter with Id '%d' already done" % packet_id)

    async def handle_publish(self, publish_packet: PublishPacket):
        packet_id = publish_packet.variable_header.packet_id
        qos = publish_packet.qos

        incoming_message = IncomingApplicationMessage(
            packet_id,
            publish_packet.topic_name,
            qos,
            publish_packet.data,
            publish_packet.retain_flag,
        )
        incoming_message.publish_packet = publish_packet
        await self._handle_message_flow(incoming_message)
        self.logger.debug(
            "Message queue size: %d" % self.session.delivered_message_queue.qsize()
        )
