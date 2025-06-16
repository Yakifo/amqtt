"""INIT."""

__all__ = ["MQTTPacket"]

from typing import Any, TypeAlias

from amqtt.errors import AMQTTError
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.connect import ConnectPacket
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
    SUBACK,
    SUBSCRIBE,
    UNSUBACK,
    UNSUBSCRIBE,
    MQTTFixedHeader,
    MQTTPacket,
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

_P: TypeAlias = MQTTPacket[Any, Any, Any]

packet_dict: dict[int, type[_P]] = {
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


def packet_class(fixed_header: MQTTFixedHeader) -> type[_P]:
    """Return the packet class for a given fixed header.

    :param fixed_header: The fixed header of the packet.
    :type
        fixed_header: MQTTFixedHeader
    :return: The packet class for the given fixed header.
    :rtype: type[MQTTPacket]
    :raises AMQTTError: If the packet type is not recognized.
    """
    if fixed_header.packet_type not in packet_dict:
        msg = f"Unexpected packet Type '{fixed_header.packet_type}'"
        raise AMQTTError(msg)
    try:
        return packet_dict[fixed_header.packet_type]
    except KeyError as e:
        msg = f"Unexpected packet Type '{fixed_header.packet_type}'"
        raise AMQTTError(msg) from e
