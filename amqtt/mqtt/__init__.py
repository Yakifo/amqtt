# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from amqtt.errors import AMQTTException
from amqtt.mqtt.packet import (
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
from amqtt.mqtt.connect import ConnectPacket
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.disconnect import DisconnectPacket
from amqtt.mqtt.pingreq import PingReqPacket
from amqtt.mqtt.pingresp import PingRespPacket
from amqtt.mqtt.publish import PublishPacket
from amqtt.mqtt.puback import PubackPacket
from amqtt.mqtt.pubrec import PubrecPacket
from amqtt.mqtt.pubrel import PubrelPacket
from amqtt.mqtt.pubcomp import PubcompPacket
from amqtt.mqtt.subscribe import SubscribePacket
from amqtt.mqtt.suback import SubackPacket
from amqtt.mqtt.unsubscribe import UnsubscribePacket
from amqtt.mqtt.unsuback import UnsubackPacket

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
