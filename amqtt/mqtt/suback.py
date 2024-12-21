# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from amqtt.adapters import ReaderAdapter
from amqtt.codecs import bytes_to_int, int_to_bytes, read_or_raise
from amqtt.errors import AMQTTException, NoDataException
from amqtt.mqtt.packet import (
    SUBACK,
    MQTTFixedHeader,
    MQTTPacket,
    MQTTPayload,
    MQTTVariableHeader,
    PacketIdVariableHeader,
)


class SubackPayload(MQTTPayload):
    __slots__ = ("return_codes",)

    RETURN_CODE_00 = 0x00
    RETURN_CODE_01 = 0x01
    RETURN_CODE_02 = 0x02
    RETURN_CODE_80 = 0x80

    def __init__(self, return_codes=None) -> None:
        super().__init__()
        self.return_codes = return_codes or []

    def __repr__(self) -> str:
        return type(self).__name__ + f"(return_codes={self.return_codes!r})"

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader,
        variable_header: MQTTVariableHeader,
    ):
        out = b""
        for return_code in self.return_codes:
            out += int_to_bytes(return_code, 1)
        return out

    @classmethod
    async def from_stream(
        cls,
        reader: ReaderAdapter,
        fixed_header: MQTTFixedHeader,
        variable_header: MQTTVariableHeader,
    ):
        return_codes = []
        bytes_to_read = fixed_header.remaining_length - variable_header.bytes_length
        for _i in range(bytes_to_read):
            try:
                return_code_byte = await read_or_raise(reader, 1)
                return_code = bytes_to_int(return_code_byte)
                return_codes.append(return_code)
            except NoDataException:
                break
        return cls(return_codes)


class SubackPacket(MQTTPacket):
    VARIABLE_HEADER = PacketIdVariableHeader
    PAYLOAD = SubackPayload

    def __init__(
        self,
        fixed: MQTTFixedHeader = None,
        variable_header: PacketIdVariableHeader = None,
        payload=None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(SUBACK, 0x00)
        else:
            if fixed.packet_type is not SUBACK:
                msg = f"Invalid fixed packet type {fixed.packet_type} for SubackPacket init"
                raise AMQTTException(
                    msg,
                )
            header = fixed

        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @classmethod
    def build(cls, packet_id, return_codes):
        variable_header = cls.VARIABLE_HEADER(packet_id)
        payload = cls.PAYLOAD(return_codes)
        return cls(variable_header=variable_header, payload=payload)
