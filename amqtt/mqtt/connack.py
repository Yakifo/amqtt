# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
# Required for type hints in classes that self reference for python < v3.10
from __future__ import annotations
from typing import Optional

from amqtt.mqtt.packet import CONNACK, MQTTPacket, MQTTFixedHeader, MQTTVariableHeader
from amqtt.codecs import read_or_raise, bytes_to_int
from amqtt.errors import AMQTTException
from amqtt.adapters import ReaderAdapter

CONNECTION_ACCEPTED: int = 0x00
UNACCEPTABLE_PROTOCOL_VERSION: int = 0x01
IDENTIFIER_REJECTED: int = 0x02
SERVER_UNAVAILABLE: int = 0x03
BAD_USERNAME_PASSWORD: int = 0x04
NOT_AUTHORIZED: int = 0x05


class ConnackVariableHeader(MQTTVariableHeader):

    __slots__ = ("session_parent", "return_code")

    session_parent: Optional[int]
    return_code: Optional[int]

    def __init__(
        self, session_parent: Optional[int] = None, return_code: Optional[int] = None
    ) -> None:
        super().__init__()
        self.session_parent = session_parent
        self.return_code = return_code

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter, fixed_header: MQTTFixedHeader):
        data = await read_or_raise(reader, 2)
        session_parent = data[0] & 0x01
        return_code = bytes_to_int(data[1])
        return cls(session_parent, return_code)

    def to_bytes(self):
        out = bytearray(2)
        # Connect acknowledge flags
        if self.session_parent:
            out[0] = 1
        else:
            out[0] = 0
        # return code
        out[1] = self.return_code

        return out

    def __repr__(self):
        return type(self).__name__ + "(session_parent={}, return_code={})".format(
            hex(self.session_parent), hex(self.return_code)
        )


class ConnackPacket(MQTTPacket):
    VARIABLE_HEADER = ConnackVariableHeader
    PAYLOAD = None

    @property
    def return_code(self) -> int:
        return self.variable_header.return_code

    @return_code.setter
    def return_code(self, return_code: int):
        self.variable_header.return_code = return_code

    @property
    def session_parent(self) -> int:
        return self.variable_header.session_parent

    @session_parent.setter
    def session_parent(self, session_parent: int):
        self.variable_header.session_parent = session_parent

    def __init__(
        self,
        fixed: Optional[MQTTFixedHeader] = None,
        variable_header: Optional[ConnackVariableHeader] = None,
        payload=None,
    ):
        if fixed is None:
            header = MQTTFixedHeader(CONNACK, 0x00)
        else:
            if fixed.packet_type is not CONNACK:
                raise AMQTTException(
                    "Invalid fixed packet type %s for ConnackPacket init"
                    % fixed.packet_type
                )
            header = fixed
        super().__init__(header)
        self.variable_header = variable_header
        self.payload = None

    @classmethod
    def build(
        cls, session_parent: int = None, return_code: int = None
    ) -> ConnackPacket:
        v_header = ConnackVariableHeader(session_parent, return_code)
        packet = ConnackPacket(variable_header=v_header)
        return packet
