import asyncio
from typing_extensions import Self

from amqtt.adapters import ReaderAdapter
from amqtt.codecs_amqtt import decode_packet_id, decode_string, encode_string, int_to_bytes
from amqtt.errors import AMQTTError, MQTTError
from amqtt.mqtt.packet import PUBLISH, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader


class PublishVariableHeader(MQTTVariableHeader):
    __slots__ = ("packet_id", "topic_name")

    def __init__(self, topic_name: str, packet_id: int | None = None) -> None:
        super().__init__()
        if "*" in topic_name:
            msg = "[MQTT-3.3.2-2] Topic name in the PUBLISH Packet MUST NOT contain wildcard characters."
            raise MQTTError(msg)
        self.topic_name = topic_name
        self.packet_id = packet_id

    def __repr__(self) -> str:
        """Return a string representation of the PublishVariableHeader object."""
        return f"{type(self).__name__}(topic={self.topic_name}, packet_id={self.packet_id})"

    def to_bytes(self) -> bytes | bytearray:
        out = bytearray()
        out.extend(encode_string(self.topic_name))
        if self.packet_id is not None:
            out.extend(int_to_bytes(self.packet_id, 2))
        return out

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter | asyncio.StreamReader, fixed_header: MQTTFixedHeader) -> Self:
        topic_name = await decode_string(reader)
        has_qos = (fixed_header.flags >> 1) & 0x03
        packet_id = await decode_packet_id(reader) if has_qos else None
        return cls(topic_name, packet_id)


class PublishPayload(MQTTPayload[MQTTVariableHeader]):
    __slots__ = ("data",)

    def __init__(self, data: bytes | None = None) -> None:
        super().__init__()
        self.data = data

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: MQTTVariableHeader | None = None,
    ) -> bytes:
        return self.data if self.data is not None else b""

    @classmethod
    async def from_stream(
        cls,
        reader: asyncio.StreamReader | ReaderAdapter,
        fixed_header: MQTTFixedHeader | None,
        variable_header: MQTTVariableHeader | None,
    ) -> Self:
        data = bytearray()
        if fixed_header is None or variable_header is None:
            msg = "Fixed header or variable header cannot be None"
            raise ValueError(msg)

        data_length = fixed_header.remaining_length - variable_header.bytes_length
        length_read = 0
        while length_read < data_length:
            buffer = await reader.read(data_length - length_read)
            data.extend(buffer)
            length_read = len(data)
        return cls(bytes(data))

    def __repr__(self) -> str:
        """Return a string representation of the PublishPayload object."""
        return f"{type(self).__name__}(data={repr(self.data)!r})"


class PublishPacket(MQTTPacket[PublishVariableHeader, PublishPayload, MQTTFixedHeader]):
    VARIABLE_HEADER = PublishVariableHeader
    PAYLOAD = PublishPayload

    DUP_FLAG = 0x08
    RETAIN_FLAG = 0x01
    QOS_FLAG = 0x06

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PublishVariableHeader | None = None,
        payload: PublishPayload | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(PUBLISH, 0x00)
        elif fixed.packet_type != PUBLISH:
            msg = f"Invalid fixed packet type {fixed.packet_type} for PublishPacket init"
            raise AMQTTError(msg) from None
        else:
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, topic_name: str, message: bytes, packet_id: int | None, dup_flag: bool, qos: int | None, retain: bool) -> Self:
        v_header = PublishVariableHeader(topic_name, packet_id)
        payload = PublishPayload(message)
        packet = cls(variable_header=v_header, payload=payload)
        packet.dup_flag = dup_flag
        packet.retain_flag = retain
        packet.qos = qos or 0
        return packet

    def set_flags(self, dup_flag: bool = False, qos: int = 0, retain_flag: bool = False) -> None:
        self.dup_flag = dup_flag
        self.retain_flag = retain_flag
        self.qos = qos

    def _set_header_flag(self, val: bool, mask: int) -> None:
        if val:
            self.fixed_header.flags |= mask
        else:
            self.fixed_header.flags &= ~mask

    def _get_header_flag(self, mask: int) -> bool:
        return bool(self.fixed_header.flags & mask)

    @property
    def dup_flag(self) -> bool:
        return self._get_header_flag(self.DUP_FLAG)

    @dup_flag.setter
    def dup_flag(self, val: bool) -> None:
        self._set_header_flag(val, self.DUP_FLAG)

    @property
    def retain_flag(self) -> bool:
        return self._get_header_flag(self.RETAIN_FLAG)

    @retain_flag.setter
    def retain_flag(self, val: bool) -> None:
        self._set_header_flag(val, self.RETAIN_FLAG)

    @property
    def qos(self) -> int | None:
        return (self.fixed_header.flags & self.QOS_FLAG) >> 1

    @qos.setter
    def qos(self, val: int) -> None:
        self.fixed_header.flags &= 0xF9
        self.fixed_header.flags |= val << 1

    @property
    def packet_id(self) -> int | None:
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

    @property
    def data(self) -> bytes | None:
        if self.payload is None:
            msg = "Payload header is not set"
            raise ValueError(msg)
        return self.payload.data

    @data.setter
    def data(self, data: bytes) -> None:
        if self.payload is None:
            msg = "Payload header is not set"
            raise ValueError(msg)
        self.payload.data = data

    @property
    def topic_name(self) -> str | None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.topic_name

    @topic_name.setter
    def topic_name(self, name: str) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.topic_name = name
