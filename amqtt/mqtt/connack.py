# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
from amqtt.adapters import ReaderAdapter
from amqtt.codecs import bytes_to_int, read_or_raise
from amqtt.errors import AMQTTException
from amqtt.mqtt.packet import CONNACK, MQTTFixedHeader, MQTTPacket, MQTTVariableHeader

CONNECTION_ACCEPTED = 0x00
UNACCEPTABLE_PROTOCOL_VERSION = 0x01
IDENTIFIER_REJECTED = 0x02
SERVER_UNAVAILABLE = 0x03
BAD_USERNAME_PASSWORD = 0x04
NOT_AUTHORIZED = 0x05


class ConnackVariableHeader(MQTTVariableHeader):
    __slots__ = ("return_code", "session_parent")

    def __init__(self, session_parent=None, return_code=None) -> None:
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

    def __repr__(self) -> str:
        return type(self).__name__ + f"(session_parent={hex(self.session_parent)}, return_code={hex(self.return_code)})"


class ConnackPacket(MQTTPacket):
    VARIABLE_HEADER = ConnackVariableHeader
    PAYLOAD = None

    @property
    def return_code(self):
        return self.variable_header.return_code

    @return_code.setter
    def return_code(self, return_code) -> None:
        self.variable_header.return_code = return_code

    @property
    def session_parent(self):
        return self.variable_header.session_parent

    @session_parent.setter
    def session_parent(self, session_parent) -> None:
        self.variable_header.session_parent = session_parent

    def __init__(
        self,
        fixed: MQTTFixedHeader = None,
        variable_header: ConnackVariableHeader = None,
        payload=None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(CONNACK, 0x00)
        else:
            if fixed.packet_type is not CONNACK:
                msg = f"Invalid fixed packet type {fixed.packet_type} for ConnackPacket init"
                raise AMQTTException(
                    msg,
                )
            header = fixed
        super().__init__(header)
        self.variable_header = variable_header
        self.payload = None

    @classmethod
    def build(cls, session_parent=None, return_code=None):
        v_header = ConnackVariableHeader(session_parent, return_code)
        return ConnackPacket(variable_header=v_header)
