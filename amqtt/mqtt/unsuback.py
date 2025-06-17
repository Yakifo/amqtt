from typing_extensions import Self

from amqtt.errors import AMQTTError
from amqtt.mqtt.packet import UNSUBACK, MQTTFixedHeader, MQTTPacket, PacketIdVariableHeader


class UnsubackPacket(MQTTPacket[PacketIdVariableHeader, None, MQTTFixedHeader]):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = None

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PacketIdVariableHeader | None = None,
        payload: None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(UNSUBACK, 0x00)
        else:
            if fixed.packet_type is not UNSUBACK:
                msg = f"Invalid fixed packet type {fixed.packet_type} for UnsubackPacket init"
                raise AMQTTError(
                    msg,
                )
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, packet_id: int) -> Self:
        variable_header = PacketIdVariableHeader(packet_id)
        return cls(variable_header=variable_header)
