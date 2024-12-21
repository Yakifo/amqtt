# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from amqtt.errors import AMQTTException
from amqtt.mqtt.packet import (
    PUBACK,
    MQTTFixedHeader,
    MQTTPacket,
    PacketIdVariableHeader,
)


class PubackPacket(MQTTPacket):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = None

    @property
    def packet_id(self):
        return self.variable_header.packet_id

    @packet_id.setter
    def packet_id(self, val: int) -> None:
        self.variable_header.packet_id = val

    def __init__(
        self,
        fixed: MQTTFixedHeader = None,
        variable_header: PacketIdVariableHeader = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(PUBACK, 0x00)
        else:
            if fixed.packet_type is not PUBACK:
                msg = f"Invalid fixed packet type {fixed.packet_type} for PubackPacket init"
                raise AMQTTException(
                    msg,
                )
            header = fixed
        super().__init__(header)
        self.variable_header = variable_header
        self.payload = None

    @classmethod
    def build(cls, packet_id: int):
        v_header = PacketIdVariableHeader(packet_id)
        return PubackPacket(variable_header=v_header)
