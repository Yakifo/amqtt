# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from amqtt.errors import AMQTTException
from amqtt.mqtt.packet import (
    UNSUBACK,
    MQTTFixedHeader,
    MQTTPacket,
    PacketIdVariableHeader,
)


class UnsubackPacket(MQTTPacket):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = None

    def __init__(
        self,
        fixed: MQTTFixedHeader = None,
        variable_header: PacketIdVariableHeader = None,
        payload=None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(UNSUBACK, 0x00)
        else:
            if fixed.packet_type is not UNSUBACK:
                msg = f"Invalid fixed packet type {fixed.packet_type} for UnsubackPacket init"
                raise AMQTTException(
                    msg,
                )
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, packet_id):
        variable_header = PacketIdVariableHeader(packet_id)
        return cls(variable_header=variable_header)
