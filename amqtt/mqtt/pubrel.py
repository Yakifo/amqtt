from typing_extensions import Self

from amqtt.errors import AMQTTError
from amqtt.mqtt.packet import PUBREL, MQTTFixedHeader, MQTTPacket, PacketIdVariableHeader


class PubrelPacket(MQTTPacket[PacketIdVariableHeader, None, MQTTFixedHeader]):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = None

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PacketIdVariableHeader | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(PUBREL, 0x02)  # [MQTT-3.6.1-1]
        else:
            if fixed.packet_type is not PUBREL:
                msg = f"Invalid fixed packet type {fixed.packet_type} for PubrelPacket init"
                raise AMQTTError(msg)
            header = fixed
        super().__init__(header)
        self.variable_header = variable_header
        self.payload = None

    @classmethod
    def build(cls, packet_id: int) -> Self:
        variable_header = PacketIdVariableHeader(packet_id)
        return cls(variable_header=variable_header)

    @property
    def packet_id(self) -> int:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.packet_id

    @packet_id.setter
    def packet_id(self, val: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.packet_id = val
