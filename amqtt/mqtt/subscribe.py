import asyncio
from typing_extensions import Self

from amqtt.adapters import ReaderAdapter
from amqtt.codecs_amqtt import bytes_to_int, decode_string, encode_string, int_to_bytes, read_or_raise
from amqtt.errors import AMQTTError, NoDataError
from amqtt.mqtt.packet import SUBSCRIBE, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader, PacketIdVariableHeader


class SubscribePayload(MQTTPayload[MQTTVariableHeader]):
    __slots__ = ("topics",)

    def __init__(self, topics: list[tuple[str, int]] | None = None) -> None:
        super().__init__()
        self.topics = topics or []

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: MQTTVariableHeader | None = None,
    ) -> bytes:
        out = b""
        for topic in self.topics:
            out += encode_string(topic[0])
            out += int_to_bytes(topic[1], 1)
        return out

    @classmethod
    async def from_stream(
        cls,
        reader: asyncio.StreamReader | ReaderAdapter,
        fixed_header: MQTTFixedHeader | None,
        variable_header: MQTTVariableHeader | None,
    ) -> Self:
        topics = []
        if fixed_header is None or variable_header is None:
            msg = "Fixed header or variable header cannot be None"
            raise ValueError(msg)

        payload_length = fixed_header.remaining_length - variable_header.bytes_length
        read_bytes = 0
        while read_bytes < payload_length:
            try:
                topic = await decode_string(reader)
                qos_byte = await read_or_raise(reader, 1)
                qos = bytes_to_int(qos_byte)
                topics.append((topic, qos))
                read_bytes += 2 + len(topic.encode("utf-8")) + 1
            except NoDataError:
                break
        return cls(topics)

    def __repr__(self) -> str:
        """Return a string representation of the SubscribePayload object."""
        return type(self).__name__ + f"(topics={self.topics!r})"


class SubscribePacket(MQTTPacket[PacketIdVariableHeader, SubscribePayload, MQTTFixedHeader]):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = SubscribePayload

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PacketIdVariableHeader | None = None,
        payload: SubscribePayload | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(SUBSCRIBE, 0x02)  # [MQTT-3.8.1-1]
        else:
            if fixed.packet_type is not SUBSCRIBE:
                msg = f"Invalid fixed packet type {fixed.packet_type} for SubscribePacket init"
                raise AMQTTError(msg)
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, topics: list[tuple[str, int]], packet_id: int) -> Self:
        v_header = PacketIdVariableHeader(packet_id)
        payload = SubscribePayload(topics)
        return cls(variable_header=v_header, payload=payload)
