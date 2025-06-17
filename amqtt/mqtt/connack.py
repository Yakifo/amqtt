from typing_extensions import Self

from amqtt.adapters import ReaderAdapter
from amqtt.codecs_amqtt import bytes_to_int, read_or_raise
from amqtt.errors import AMQTTError
from amqtt.mqtt.packet import CONNACK, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader

CONNECTION_ACCEPTED = 0x00
UNACCEPTABLE_PROTOCOL_VERSION = 0x01
IDENTIFIER_REJECTED = 0x02
SERVER_UNAVAILABLE = 0x03
BAD_USERNAME_PASSWORD = 0x04
NOT_AUTHORIZED = 0x05


class ConnackVariableHeader(MQTTVariableHeader):
    __slots__ = ("return_code", "session_parent")

    def __init__(self, session_parent: int | None = None, return_code: int | None = None) -> None:
        super().__init__()
        self.session_parent = session_parent
        self.return_code = return_code

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter, _: MQTTFixedHeader | None) -> Self:
        data = await read_or_raise(reader, 2)
        session_parent = data[0] & 0x01
        return_code = bytes_to_int(data[1])
        return cls(session_parent, return_code)

    def to_bytes(self) -> bytes | bytearray:
        out = bytearray(2)
        # Connect acknowledge flags
        out[0] = 1 if self.session_parent else 0
        # Return code
        out[1] = self.return_code or 0
        return out

    def __repr__(self) -> str:
        """Return a string representation of the ConnackVariableHeader object."""
        return f"{type(self).__name__}(session_parent={hex(self.session_parent or 0)}, return_code={hex(self.return_code or 0)})"


class ConnackPacket(MQTTPacket[ConnackVariableHeader, MQTTPayload[MQTTVariableHeader], MQTTFixedHeader]):
    VARIABLE_HEADER = ConnackVariableHeader
    PAYLOAD = MQTTPayload[MQTTVariableHeader]

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: ConnackVariableHeader | None = None,
        payload: MQTTPayload[MQTTVariableHeader] | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(CONNACK, 0x00)
        elif fixed.packet_type != CONNACK:
            msg = f"Invalid fixed packet type {fixed.packet_type} for ConnackPacket init"
            raise AMQTTError(msg) from None
        else:
            header = fixed

        super().__init__(header, variable_header, payload)

    @classmethod
    def build(cls, session_parent: int | None = None, return_code: int | None = None) -> Self:
        v_header = ConnackVariableHeader(session_parent, return_code)
        return cls(variable_header=v_header)

    @property
    def return_code(self) -> int | None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.return_code

    @return_code.setter
    def return_code(self, return_code: int | None) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.return_code = return_code

    @property
    def session_parent(self) -> int | None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.session_parent

    @session_parent.setter
    def session_parent(self, session_parent: int | None) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.session_parent = session_parent
