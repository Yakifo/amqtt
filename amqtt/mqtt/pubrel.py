# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from __future__ import annotations
from typing import Optional

from amqtt.mqtt.packet import (
    MQTTPacket,
    MQTTFixedHeader,
    PUBREL,
    PacketIdVariableHeader,
)
from amqtt.errors import AMQTTException


class PubrelPacket(MQTTPacket):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = None

    variable_header: Optional[PacketIdVariableHeader]
    payload: None

    @property
    def packet_id(self) -> int:
        return self.variable_header.packet_id

    @packet_id.setter
    def packet_id(self, val: int):
        self.variable_header.packet_id = val

    def __init__(
        self,
        fixed: MQTTFixedHeader = None,
        variable_header: Optional[PacketIdVariableHeader] = None,
    ):
        if fixed is None:
            header = MQTTFixedHeader(PUBREL, 0x02)  # [MQTT-3.6.1-1]
        else:
            if fixed.packet_type is not PUBREL:
                raise AMQTTException(
                    "Invalid fixed packet type %s for PubrelPacket init"
                    % fixed.packet_type
                )
            header = fixed
        super().__init__(header)
        self.variable_header = variable_header
        self.payload = None

    @classmethod
    def build(cls, packet_id) -> PubrelPacket:
        variable_header = PacketIdVariableHeader(packet_id)
        return PubrelPacket(variable_header=variable_header)
