import asyncio
from typing_extensions import Self

from amqtt.adapters import ReaderAdapter
from amqtt.codecs_amqtt import bytes_to_int, int_to_bytes, read_or_raise
from amqtt.errors import AMQTTError, NoDataError
from amqtt.mqtt.packet import SUBACK, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader, PacketIdVariableHeader


class SubackPayload(MQTTPayload[MQTTVariableHeader]):
    __slots__ = ("return_codes",)

    RETURN_CODE_00 = 0x00
    RETURN_CODE_01 = 0x01
    RETURN_CODE_02 = 0x02
    RETURN_CODE_80 = 0x80

    def __init__(self, return_codes: list[int] | None = None) -> None:
        super().__init__()
        self.return_codes = return_codes or []

    def __repr__(self) -> str:
        """Return a string representation of the SubackPayload object."""
        return f"{type(self).__name__}(return_codes={self.return_codes!r})"

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: MQTTVariableHeader | None = None,
    ) -> bytes:
        out = b""
        for return_code in self.return_codes:
            out += int_to_bytes(return_code, 1)
        return out

    @classmethod
    async def from_stream(
        cls,
        reader: asyncio.StreamReader | ReaderAdapter,
        fixed_header: MQTTFixedHeader | None,
        variable_header: MQTTVariableHeader | None,
    ) -> Self:
        return_codes = []
        if fixed_header is None or variable_header is None:
            msg = "Fixed header or variable header cannot be None"
            raise AMQTTError(msg)

        bytes_to_read = fixed_header.remaining_length - variable_header.bytes_length
        for _ in range(bytes_to_read):
            try:
                return_code_byte = await read_or_raise(reader, 1)
                return_code = bytes_to_int(return_code_byte)
                return_codes.append(return_code)
            except NoDataError:
                break
        return cls(return_codes)


class SubackPacket(MQTTPacket[PacketIdVariableHeader, SubackPayload, MQTTFixedHeader]):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = SubackPayload

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: PacketIdVariableHeader | None = None,
        payload: SubackPayload | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(SUBACK, 0x00)
        else:
            if fixed.packet_type is not SUBACK:
                msg = f"Invalid fixed packet type {fixed.packet_type} for SubackPacket init"
                raise AMQTTError(msg)
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, packet_id: int, return_codes: list[int]) -> Self:
        variable_header = cls.VARIABLE_HEADER(packet_id)
        payload = cls.PAYLOAD(return_codes)
        return cls(variable_header=variable_header, payload=payload)
