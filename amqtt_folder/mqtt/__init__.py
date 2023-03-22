# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from amqtt_folder.errors import AMQTTException
from amqtt_folder.mqtt.packet import (
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
    MQTTFixedHeader,
)
from amqtt_folder.mqtt.connect import ConnectPacket
from amqtt_folder.mqtt.connack import ConnackPacket
from amqtt_folder.mqtt.disconnect import DisconnectPacket
from amqtt_folder.mqtt.pingreq import PingReqPacket
from amqtt_folder.mqtt.pingresp import PingRespPacket
from amqtt_folder.mqtt.publish import PublishPacket
from amqtt_folder.mqtt.puback import PubackPacket
from amqtt_folder.mqtt.pubrec import PubrecPacket
from amqtt_folder.mqtt.pubrel import PubrelPacket
from amqtt_folder.mqtt.pubcomp import PubcompPacket
from amqtt_folder.mqtt.subscribe import SubscribePacket
from amqtt_folder.mqtt.suback import SubackPacket
from amqtt_folder.mqtt.unsubscribe import UnsubscribePacket
from amqtt_folder.mqtt.unsuback import UnsubackPacket

packet_dict = {
    CONNECT: ConnectPacket,
    CONNACK: ConnackPacket,
    PUBLISH: PublishPacket,
    PUBACK: PubackPacket,
    PUBREC: PubrecPacket,
    PUBREL: PubrelPacket,
    PUBCOMP: PubcompPacket,
    SUBSCRIBE: SubscribePacket,
    SUBACK: SubackPacket,
    UNSUBSCRIBE: UnsubscribePacket,
    UNSUBACK: UnsubackPacket,
    PINGREQ: PingReqPacket,
    PINGRESP: PingRespPacket,
    DISCONNECT: DisconnectPacket,
}


def packet_class(fixed_header: MQTTFixedHeader):
    try:
        cls = packet_dict[fixed_header.packet_type]
        return cls
    except KeyError:
        raise AMQTTException("Unexpected packet Type '%s'" % fixed_header.packet_type)
