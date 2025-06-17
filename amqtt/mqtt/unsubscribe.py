from asyncio import StreamReader
from typing_extensions import Self

from amqtt.adapters import ReaderAdapter
from amqtt.codecs_amqtt import decode_string, encode_string
from amqtt.errors import AMQTTError, NoDataError
from amqtt.mqtt.packet import UNSUBSCRIBE, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader, PacketIdVariableHeader


class UnubscribePayload(MQTTPayload[MQTTVariableHeader]):
    __slots__ = ("topics",)

    def __init__(self, topics: list[str] | None = None) -> None:
        super().__init__()
        self.topics = topics or []

    def to_bytes(self, fixed_header: MQTTFixedHeader | None = None, variable_header: MQTTVariableHeader | None = None) -> bytes:
        out = b""
        for topic in self.topics:
            out += encode_string(topic)
        return out

    @classmethod
    async def from_stream(
        cls: type[Self],
        reader: StreamReader | ReaderAdapter,
        fixed_header: MQTTFixedHeader | None,
        variable_header: MQTTVariableHeader | None,
    ) -> Self:
        if fixed_header is None or variable_header is None:
            msg = "Fixed header or Value header is not set."
            raise ValueError(msg)

        topics = []
        payload_length = fixed_header.remaining_length - variable_header.bytes_length
        read_bytes = 0
        while read_bytes < payload_length:
            try:
                topic = await decode_string(reader)
                topics.append(topic)
                read_bytes += 2 + len(topic.encode("utf-8"))
            except NoDataError:
                break
        return cls(topics)


class UnsubscribePacket(MQTTPacket[PacketIdVariableHeader, UnubscribePayload, MQTTFixedHeader]):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = UnubscribePayload

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PacketIdVariableHeader | None = None,
        payload: UnubscribePayload | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(UNSUBSCRIBE, 0x02)  # [MQTT-3.10.1-1]
        else:
            if fixed.packet_type is not UNSUBSCRIBE:
                msg = f"Invalid fixed packet type {fixed.packet_type} for UnsubscribePacket init"
                raise AMQTTError(msg)
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, topics: list[str], packet_id: int) -> "UnsubscribePacket":
        v_header = PacketIdVariableHeader(packet_id)
        payload = UnubscribePayload(topics)
        return UnsubscribePacket(variable_header=v_header, payload=payload)
