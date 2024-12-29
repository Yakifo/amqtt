from typing import Self

from amqtt.errors import AMQTTException
from amqtt.mqtt.packet import PINGRESP, MQTTFixedHeader, MQTTPacket


class PingRespPacket(MQTTPacket[None, None]):
    VARIABLE_HEADER = None
    PAYLOAD = None

    def __init__(self, fixed: MQTTFixedHeader | None = None) -> None:
        if fixed is None:
            header = MQTTFixedHeader(PINGRESP, 0x00)
        else:
            if fixed.packet_type is not PINGRESP:
                msg = f"Invalid fixed packet type {fixed.packet_type} for PingRespPacket init"
                raise AMQTTException(msg)
            header = fixed
        super().__init__(header)
        self.variable_header = None
        self.payload = None

    @classmethod
    def build(cls) -> Self:
        return cls()
