# import asyncio
# import logging
# import secrets
# from typing import Any
# import unittest

# from amqtt.adapters import StreamReaderAdapter, StreamWriterAdapter
# from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
# from amqtt.mqtt.protocol.handler import ProtocolHandler
# from amqtt.mqtt.puback import PubackPacket
# from amqtt.mqtt.pubcomp import PubcompPacket
# from amqtt.mqtt.publish import PublishPacket
# from amqtt.mqtt.pubrec import PubrecPacket
# from amqtt.mqtt.pubrel import PubrelPacket
# from amqtt.plugins.manager import PluginManager
# from amqtt.session import (
#     IncomingApplicationMessage,
#     OutgoingApplicationMessage,
#     Session,
# )

# formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
# logging.basicConfig(level=logging.DEBUG, format=formatter)
# log = logging.getLogger(__name__)


# def rand_packet_id():
#     return secrets.randbelow(65536)


# def adapt(reader, writer):
#     return StreamReaderAdapter(reader), StreamWriterAdapter(writer)


# class ProtocolHandlerTest(unittest.TestCase):
#     def setUp(self):
#         self.loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(self.loop)
#         self.plugin_manager = PluginManager("amqtt.test.plugins", context=None)

#     def tearDown(self):
#         self.loop.close()

#     def test_init_handler(self):
#         Session()
#         handler = ProtocolHandler(self.plugin_manager)
#         assert handler.session is None
#         assert handler._loop is self.loop
#         self.check_empty_waiters(handler)

#     def test_start_stop(self):
#         async def server_mock(reader, writer) -> None:
#             pass

#         async def test_coro() -> None:
#             try:
#                 s = Session()
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 handler = ProtocolHandler(self.plugin_manager)
#                 handler.attach(s, reader_adapted, writer_adapted)
#                 await self.start_handler(handler, s)
#                 await self.stop_handler(handler, s)
#                 future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         future: asyncio.Future[Any] = asyncio.Future()
#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     def test_publish_qos0(self):
#         async def server_mock(reader, writer) -> None:
#             try:
#                 packet = await PublishPacket.from_stream(reader)
#                 assert packet.variable_header.topic_name == "/topic"
#                 assert packet.qos == QOS_0
#                 assert packet.packet_id is None
#             except Exception as ae:
#                 future.set_exception(ae)

#         async def test_coro() -> None:
#             try:
#                 s = Session()
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 handler = ProtocolHandler(self.plugin_manager)
#                 handler.attach(s, reader_adapted, writer_adapted)
#                 await self.start_handler(handler, s)
#                 message = await handler.mqtt_publish(
#                     "/topic",
#                     b"test_data",
#                     QOS_0,
#                     False,
#                 )
#                 assert isinstance(message, OutgoingApplicationMessage)
#                 assert message.publish_packet is not None
#                 assert message.puback_packet is None
#                 assert message.pubrec_packet is None
#                 assert message.pubrel_packet is None
#                 assert message.pubcomp_packet is None
#                 await self.stop_handler(handler, s)
#                 future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         future: asyncio.Future[Any] = asyncio.Future()
#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     def test_publish_qos1(self):
#         self.handler: ProtocolHandler | None = None

#         async def server_mock(reader, writer) -> None:
#             packet = await PublishPacket.from_stream(reader)
#             try:
#                 assert packet.variable_header.topic_name == "/topic"
#                 assert packet.qos == QOS_1
#                 assert packet.packet_id is not None
#                 assert packet.packet_id in self.session.inflight_out
#                 assert self.handler is not None
#                 assert packet.packet_id in self.handler._puback_waiters
#                 puback = PubackPacket.build(packet.packet_id)
#                 await puback.to_stream(writer)
#             except Exception as ae:
#                 future.set_exception(ae)

#         async def test_coro() -> None:
#             try:
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 self.handler = ProtocolHandler(self.plugin_manager)
#                 self.handler.attach(self.session, reader_adapted, writer_adapted)
#                 await self.start_handler(self.handler, self.session)
#                 message = await self.handler.mqtt_publish(
#                     "/topic",
#                     b"test_data",
#                     QOS_1,
#                     False,
#                 )
#                 assert isinstance(message, OutgoingApplicationMessage)
#                 assert message.publish_packet is not None
#                 assert message.puback_packet is not None
#                 assert message.pubrec_packet is None
#                 assert message.pubrel_packet is None
#                 assert message.pubcomp_packet is None
#                 await self.stop_handler(self.handler, self.session)
#                 if not future.done():
#                     future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         self.handler = None
#         self.session = Session()
#         future: asyncio.Future[Any] = asyncio.Future()

#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     def test_publish_qos2(self):
#         async def server_mock(reader, writer) -> None:
#             try:
#                 packet = await PublishPacket.from_stream(reader)
#                 assert packet.topic_name == "/topic"
#                 assert packet.qos == QOS_2
#                 assert packet.packet_id is not None
#                 assert packet.packet_id in self.session.inflight_out
#                 assert self.handler is not None
#                 assert packet.packet_id in self.handler._pubrec_waiters
#                 pubrec = PubrecPacket.build(packet.packet_id)
#                 await pubrec.to_stream(writer)

#                 await PubrelPacket.from_stream(reader)
#                 assert packet.packet_id in self.handler._pubcomp_waiters
#                 pubcomp = PubcompPacket.build(packet.packet_id)
#                 await pubcomp.to_stream(writer)
#             except Exception as ae:
#                 future.set_exception(ae)

#         async def test_coro() -> None:
#             try:
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 self.handler = ProtocolHandler(self.plugin_manager)
#                 self.handler.attach(self.session, reader_adapted, writer_adapted)
#                 await self.start_handler(self.handler, self.session)
#                 message = await self.handler.mqtt_publish(
#                     "/topic",
#                     b"test_data",
#                     QOS_2,
#                     False,
#                 )
#                 assert isinstance(message, OutgoingApplicationMessage)
#                 assert message.publish_packet is not None
#                 assert message.puback_packet is None
#                 assert message.pubrec_packet is not None
#                 assert message.pubrel_packet is not None
#                 assert message.pubcomp_packet is not None
#                 await self.stop_handler(self.handler, self.session)
#                 if not future.done():
#                     future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         self.handler = None
#         self.session = Session()
#         future: asyncio.Future[Any] = asyncio.Future()

#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     def test_receive_qos0(self):
#         async def server_mock(reader, writer) -> None:
#             packet = PublishPacket.build(
#                 "/topic",
#                 b"test_data",
#                 rand_packet_id(),
#                 False,
#                 QOS_0,
#                 False,
#             )
#             await packet.to_stream(writer)

#         async def test_coro() -> None:
#             try:
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 self.handler = ProtocolHandler(self.plugin_manager)
#                 self.handler.attach(self.session, reader_adapted, writer_adapted)
#                 await self.start_handler(self.handler, self.session)
#                 message = await self.handler.mqtt_deliver_next_message()
#                 assert isinstance(message, IncomingApplicationMessage)
#                 assert message.publish_packet is not None
#                 assert message.puback_packet is None
#                 assert message.pubrec_packet is None
#                 assert message.pubrel_packet is None
#                 assert message.pubcomp_packet is None
#                 await self.stop_handler(self.handler, self.session)
#                 future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         self.handler = None
#         self.session = Session()
#         future: asyncio.Future[Any] = asyncio.Future()
#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     def test_receive_qos1(self):
#         async def server_mock(reader, writer) -> None:
#             try:
#                 packet = PublishPacket.build(
#                     "/topic",
#                     b"test_data",
#                     rand_packet_id(),
#                     False,
#                     QOS_1,
#                     False,
#                 )
#                 await packet.to_stream(writer)
#                 puback = await PubackPacket.from_stream(reader)
#                 assert puback is not None
#                 assert packet.packet_id == puback.packet_id
#             except Exception as ae:
#                 future.set_exception(ae)

#         async def test_coro() -> None:
#             try:
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 self.handler = ProtocolHandler(self.plugin_manager)
#                 self.handler.attach(self.session, reader_adapted, writer_adapted)
#                 await self.start_handler(self.handler, self.session)
#                 message = await self.handler.mqtt_deliver_next_message()
#                 assert isinstance(message, IncomingApplicationMessage)
#                 assert message.publish_packet is not None
#                 assert message.puback_packet is not None
#                 assert message.pubrec_packet is None
#                 assert message.pubrel_packet is None
#                 assert message.pubcomp_packet is None
#                 await self.stop_handler(self.handler, self.session)
#                 future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         self.handler = None
#         self.session = Session()
#         future: asyncio.Future[Any] = asyncio.Future()
#         self.event = asyncio.Event()
#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     def test_receive_qos2(self):
#         async def server_mock(reader, writer) -> None:
#             try:
#                 packet = PublishPacket.build(
#                     "/topic",
#                     b"test_data",
#                     rand_packet_id(),
#                     False,
#                     QOS_2,
#                     False,
#                 )
#                 await packet.to_stream(writer)
#                 pubrec = await PubrecPacket.from_stream(reader)
#                 assert pubrec is not None
#                 assert packet.packet_id == pubrec.packet_id
#                 assert self.handler is not None
#                 assert packet.packet_id in self.handler._pubrel_waiters
#                 pubrel = PubrelPacket.build(packet.packet_id)
#                 await pubrel.to_stream(writer)
#                 pubcomp = await PubcompPacket.from_stream(reader)
#                 assert pubcomp is not None
#                 assert packet.packet_id == pubcomp.packet_id
#             except Exception as ae:
#                 future.set_exception(ae)

#         async def test_coro() -> None:
#             try:
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 self.handler = ProtocolHandler(self.plugin_manager)
#                 self.handler.attach(self.session, reader_adapted, writer_adapted)
#                 await self.start_handler(self.handler, self.session)
#                 message = await self.handler.mqtt_deliver_next_message()
#                 assert isinstance(message, IncomingApplicationMessage)
#                 assert message.publish_packet is not None
#                 assert message.puback_packet is None
#                 assert message.pubrec_packet is not None
#                 assert message.pubrel_packet is not None
#                 assert message.pubcomp_packet is not None
#                 await self.stop_handler(self.handler, self.session)
#                 future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         self.handler = None
#         self.session = Session()
#         future: asyncio.Future[Any] = asyncio.Future()
#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     async def start_handler(self, handler, session):
#         self.check_empty_waiters(handler)
#         self.check_no_message(session)
#         await handler.start()
#         assert handler._reader_ready

#     async def stop_handler(self, handler, session):
#         await handler.stop()
#         assert handler._reader_stopped
#         self.check_empty_waiters(handler)
#         self.check_no_message(session)

#     def check_empty_waiters(self, handler):
#         assert not handler._puback_waiters
#         assert not handler._pubrec_waiters
#         assert not handler._pubrel_waiters
#         assert not handler._pubcomp_waiters

#     def check_no_message(self, session):
#         assert not session.inflight_out
#         assert not session.inflight_in

#     def test_publish_qos1_retry(self):
#         async def server_mock(reader, writer) -> None:
#             packet = await PublishPacket.from_stream(reader)
#             try:
#                 assert packet.topic_name == "/topic"
#                 assert packet.qos == QOS_1
#                 assert packet.packet_id is not None
#                 assert packet.packet_id in self.session.inflight_out
#                 assert self.handler is not None
#                 assert packet.packet_id in self.handler._puback_waiters
#                 puback = PubackPacket.build(packet.packet_id)
#                 await puback.to_stream(writer)
#             except Exception as ae:
#                 future.set_exception(ae)

#         async def test_coro() -> None:
#             try:
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 self.handler = ProtocolHandler(self.plugin_manager)
#                 self.handler.attach(self.session, reader_adapted, writer_adapted)
#                 await self.handler.start()
#                 await self.stop_handler(self.handler, self.session)
#                 if not future.done():
#                     future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         self.handler = None
#         self.session = Session()
#         message = OutgoingApplicationMessage(1, "/topic", QOS_1, b"test_data", False)
#         message.publish_packet = PublishPacket.build(
#             "/topic",
#             b"test_data",
#             rand_packet_id(),
#             False,
#             QOS_1,
#             False,
#         )
#         self.session.inflight_out[1] = message
#         future: asyncio.Future[Any] = asyncio.Future()

#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception

#     def test_publish_qos2_retry(self):
#         async def server_mock(reader, writer) -> None:
#             try:
#                 packet = await PublishPacket.from_stream(reader)
#                 assert packet.topic_name == "/topic"
#                 assert packet.qos == QOS_2
#                 assert packet.packet_id is not None
#                 assert packet.packet_id in self.session.inflight_out
#                 assert self.handler is not None
#                 assert packet.packet_id in self.handler._pubrec_waiters
#                 pubrec = PubrecPacket.build(packet.packet_id)
#                 await pubrec.to_stream(writer)

#                 await PubrelPacket.from_stream(reader)
#                 assert packet.packet_id in self.handler._pubcomp_waiters
#                 pubcomp = PubcompPacket.build(packet.packet_id)
#                 await pubcomp.to_stream(writer)
#             except Exception as ae:
#                 future.set_exception(ae)

#         async def test_coro() -> None:
#             try:
#                 reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
#                 reader_adapted, writer_adapted = adapt(reader, writer)
#                 self.handler = ProtocolHandler(self.plugin_manager)
#                 self.handler.attach(self.session, reader_adapted, writer_adapted)
#                 await self.handler.start()
#                 await self.stop_handler(self.handler, self.session)
#                 if not future.done():
#                     future.set_result(True)
#             except Exception as ae:
#                 future.set_exception(ae)

#         self.handler = None
#         self.session = Session()
#         message = OutgoingApplicationMessage(1, "/topic", QOS_2, b"test_data", False)
#         message.publish_packet = PublishPacket.build(
#             "/topic",
#             b"test_data",
#             rand_packet_id(),
#             False,
#             QOS_2,
#             False,
#         )
#         self.session.inflight_out[1] = message
#         future: asyncio.Future[Any] = asyncio.Future()

#         coro = asyncio.start_server(server_mock, "127.0.0.1", 8888)
#         server = self.loop.run_until_complete(coro)
#         self.loop.run_until_complete(test_coro())
#         server.close()
#         self.loop.run_until_complete(server.wait_closed())
#         exception = future.exception()
#         if exception:
#             raise exception
