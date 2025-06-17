from amqtt.errors import AMQTTError
from amqtt.mqtt.packet import DISCONNECT, MQTTFixedHeader, MQTTPacket


class DisconnectPacket(MQTTPacket[None, None, MQTTFixedHeader]):
    VARIABLE_HEADER = None
    PAYLOAD = None

    def __init__(self, fixed: MQTTFixedHeader | None = None) -> None:
        if fixed is None:
            header = MQTTFixedHeader(DISCONNECT, 0x00)
        else:
            if fixed.packet_type is not DISCONNECT:
                msg = f"Invalid fixed packet type {fixed.packet_type} for DisconnectPacket init"
                raise AMQTTError(msg)
            header = fixed
        super().__init__(header)
        self.variable_header = None
        self.payload = None
