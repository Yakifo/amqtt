from typing_extensions import Self

from amqtt.errors import AMQTTError
from amqtt.mqtt.packet import PUBACK, MQTTFixedHeader, MQTTPacket, PacketIdVariableHeader


class PubackPacket(MQTTPacket[PacketIdVariableHeader, None, MQTTFixedHeader]):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = None

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

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PacketIdVariableHeader | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(PUBACK, 0x00)
        else:
            if fixed.packet_type is not PUBACK:
                msg = f"Invalid fixed packet type {fixed.packet_type} for PubackPacket init"
                raise AMQTTError(msg)
            header = fixed

        super().__init__(header, variable_header, None)

    @classmethod
    def build(cls, packet_id: int) -> Self:
        v_header = PacketIdVariableHeader(packet_id)
        return cls(variable_header=v_header)
