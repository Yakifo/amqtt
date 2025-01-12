from amqtt.errors import AMQTTError
from amqtt.mqtt.packet import PINGREQ, MQTTFixedHeader, MQTTPacket


class PingReqPacket(MQTTPacket[None, None, MQTTFixedHeader]):
    VARIABLE_HEADER = None
    PAYLOAD = None

    def __init__(self, fixed: MQTTFixedHeader | None = None) -> None:
        if fixed is None:
            header = MQTTFixedHeader(PINGREQ, 0x00)
        else:
            if fixed.packet_type is not PINGREQ:
                msg = f"Invalid fixed packet type {fixed.packet_type} for PingReqPacket init"
                raise AMQTTError(msg)
            header = fixed
        super().__init__(header)
        self.variable_header = None
        self.payload = None
