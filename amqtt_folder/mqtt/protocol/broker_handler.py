# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from asyncio import futures, Queue
from amqtt_folder.mqtt.protocol.handler import ProtocolHandler
from amqtt_folder.mqtt.connack import (
    CONNECTION_ACCEPTED,
    UNACCEPTABLE_PROTOCOL_VERSION,
    IDENTIFIER_REJECTED,
    BAD_USERNAME_PASSWORD,
    NOT_AUTHORIZED,
    ConnackPacket,
)
from amqtt_folder.mqtt.connect import ConnectPacket
from amqtt_folder.mqtt.pingreq import PingReqPacket
from amqtt_folder.mqtt.pingresp import PingRespPacket
from amqtt_folder.mqtt.subscribe import SubscribePacket
from amqtt_folder.mqtt.publish import PublishPacket
from amqtt_folder.mqtt.suback import SubackPacket
from amqtt_folder.mqtt.unsubscribe import UnsubscribePacket
from amqtt_folder.mqtt.unsuback import UnsubackPacket
from amqtt_folder.utils import format_client_message
from amqtt_folder.session import Session
from amqtt_folder.plugins.manager import PluginManager
from amqtt_folder.adapters import ReaderAdapter, WriterAdapter
from amqtt_folder.errors import MQTTException
from .handler import EVENT_MQTT_PACKET_RECEIVED, EVENT_MQTT_PACKET_SENT

from amqtt_folder.clientconnection import pushRowToDatabase, updateRowFromDatabase

"""START:29MART2023 - Burcu"""
from amqtt_folder.codecs import (
    encode_string,
    bytes_to_hex_str, 
    decode_string
)

"""STOP:29MART2023 - Burcu"""
from diffiehellman import DiffieHellman
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
        self.logger.debug("#######session client ID %s", self.session.client_id) #Burcu
        subscription = {
            "packet_id": subscribe.variable_header.packet_id,
            "topics": subscribe.payload.topics,
        }
        self.logger.debug("#######Inside hande_subscribe in broker_handler.py" )
        await self._pending_subscriptions.put(subscription)
    
    """ Burcu: START 29mart2023 te eklendi """    
    async def broker_df_publish (self, topicname, data):
        self.logger.debug("#######102 topic name, %s", topicname )
        if (topicname == self.session.client_id):
            try:
                dh1 = DiffieHellman(group=14, key_bits=540)
                dh1_public = dh1.get_public_key()
                dh1_public_hex = bytes_to_hex_str(dh1_public)
                self.logger.debug("#######107 broker public key %s", dh1_public_hex)
                self.session.session_info.dh = dh1
            except Exception as e:
                self.logger.warning("YYYYYYYYYYY %r", e.args)
            try:
                await self.mqtt_publish(topicname, data = encode_string(dh1_public_hex), qos=2, retain= False )
                self.session.session_info.key_establishment_state = 4
                
                self.logger.debug("#######108 self.session.session_info.key_establishment_state, %s", self.session.session_info.key_establishment_state )
            except Exception as e2:
                self.logger.warning("XXXXXXXXXXXX %r ", e2.args)
   
            self.logger.debug("#######session state %s", self.session.session_info.key_establishment_state)

        elif (topicname == "AuthenticationTopic"):
            self.logger.debug("#######127 client public key %s", data)
            dh1 = self.session.session_info.dh
            dh1_shared = dh1.generate_shared_key(data)
            self.logger.debug("#######129 shared key %s", dh1_shared)


            

        """

    async def broker_shared_generated (self, dh1_public, dh1):

        try:
            dh1_shared = dh1.generate_shared_key(dh1_public)
        except Exception as e:
            self.logger.warning("YYYYYYYYYYY %r", e.args)   
        
        self.logger.debug("#######Inside broker_shared_generated in broker_handler.py" )
        self.logger.debug("#######session state %s", self.session.session_info.key_establishment_state)
        self.logger.debug("#######dh1_shared %s", dh1_shared)
"""
   
    """ Burcu: START 29mart2023 te eklendi """    

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

        #modification --> client info added, ke state is currently equal to 0, other fields are none right now.
        incoming_session.session_info.client_id = connect.client_id
         #Burcu-29Mart

        #call push to database from clientconnection.py to create the record of this session with the related key pairs, session states and created session keys
        pushRowToDatabase(incoming_session.session_info.client_id, incoming_session.session_info.key_establishment_state, 
                          incoming_session.session_info.client_spec_pub_key, incoming_session.session_info.client_spec_priv_key, 
                          incoming_session.session_info.session_key)
        

        if connect.keep_alive > 0:
            incoming_session.keep_alive = connect.keep_alive
        else:
            incoming_session.keep_alive = 0

        handler = cls(plugins_manager, loop=loop)
        return handler, incoming_session
