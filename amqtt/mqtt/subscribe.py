# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import asyncio

from amqtt.codecs import (
    bytes_to_int,
    decode_string,
    encode_string,
    int_to_bytes,
    read_or_raise,
)
from amqtt.errors import AMQTTException, NoDataException
from amqtt.mqtt.packet import (
    SUBSCRIBE,
    MQTTFixedHeader,
    MQTTPacket,
    MQTTPayload,
    MQTTVariableHeader,
    PacketIdVariableHeader,
)


class SubscribePayload(MQTTPayload):
    __slots__ = ("topics",)

    def __init__(self, topics=None) -> None:
        super().__init__()
        self.topics = topics or []

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader,
        variable_header: MQTTVariableHeader,
    ):
        out = b""
        for topic in self.topics:
            out += encode_string(topic[0])
            out += int_to_bytes(topic[1], 1)
        return out

    @classmethod
    async def from_stream(
        cls,
        reader: asyncio.StreamReader,
        fixed_header: MQTTFixedHeader,
        variable_header: MQTTVariableHeader,
    ):
        topics = []
        payload_length = fixed_header.remaining_length - variable_header.bytes_length
        read_bytes = 0
        while read_bytes < payload_length:
            try:
                topic = await decode_string(reader)
                qos_byte = await read_or_raise(reader, 1)
                qos = bytes_to_int(qos_byte)
                topics.append((topic, qos))
                read_bytes += 2 + len(topic.encode("utf-8")) + 1
            except NoDataException:
                break
        return cls(topics)

    def __repr__(self) -> str:
        return type(self).__name__ + f"(topics={self.topics!r})"


class SubscribePacket(MQTTPacket):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = SubscribePayload

    def __init__(
        self,
        fixed: MQTTFixedHeader = None,
        variable_header: PacketIdVariableHeader = None,
        payload=None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(SUBSCRIBE, 0x02)  # [MQTT-3.8.1-1]
        else:
            if fixed.packet_type is not SUBSCRIBE:
                msg = f"Invalid fixed packet type {fixed.packet_type} for SubscribePacket init"
                raise AMQTTException(
                    msg,
                )
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, topics, packet_id):
        v_header = PacketIdVariableHeader(packet_id)
        payload = SubscribePayload(topics)
        return SubscribePacket(variable_header=v_header, payload=payload)
