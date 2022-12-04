# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from __future__ import annotations
from typing import Optional

from amqtt.mqtt.packet import (
    MQTTPacket,
    MQTTFixedHeader,
    UNSUBACK,
    PacketIdVariableHeader,
)
from amqtt.errors import AMQTTException


class UnsubackPacket(MQTTPacket):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = None

    variable_header: Optional[PacketIdVariableHeader]
    payload: None

    def __init__(
        self,
        fixed: Optional[MQTTFixedHeader] = None,
        variable_header: Optional[PacketIdVariableHeader] = None,
        payload=None,
    ):
        if fixed is None:
            header = MQTTFixedHeader(UNSUBACK, 0x00)
        else:
            if fixed.packet_type is not UNSUBACK:
                raise AMQTTException(
                    "Invalid fixed packet type %s for UnsubackPacket init"
                    % fixed.packet_type
                )
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, packet_id) -> UnsubackPacket:
        variable_header = PacketIdVariableHeader(packet_id)
        return cls(variable_header=variable_header)
