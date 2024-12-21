# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from amqtt.errors import AMQTTException
from amqtt.mqtt.packet import DISCONNECT, MQTTFixedHeader, MQTTPacket


class DisconnectPacket(MQTTPacket):
    VARIABLE_HEADER = None
    PAYLOAD = None

    def __init__(self, fixed: MQTTFixedHeader = None) -> None:
        if fixed is None:
            header = MQTTFixedHeader(DISCONNECT, 0x00)
        else:
            if fixed.packet_type is not DISCONNECT:
                msg = f"Invalid fixed packet type {fixed.packet_type} for DisconnectPacket init"
                raise AMQTTException(
                    msg,
                )
            header = fixed
        super().__init__(header)
        self.variable_header = None
        self.payload = None
