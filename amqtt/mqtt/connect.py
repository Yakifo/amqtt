from asyncio import StreamReader
from typing_extensions import Self

from amqtt.adapters import ReaderAdapter
from amqtt.codecs_amqtt import (
    bytes_to_int,
    decode_data_with_length,
    decode_string,
    encode_data_with_length,
    encode_string,
    int_to_bytes,
    read_or_raise,
)
from amqtt.errors import AMQTTError, NoDataError
from amqtt.mqtt.packet import CONNECT, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader
from amqtt.utils import gen_client_id


class ConnectVariableHeader(MQTTVariableHeader):
    __slots__ = ("flags", "keep_alive", "proto_level", "proto_name")

    USERNAME_FLAG = 0x80
    PASSWORD_FLAG = 0x40
    WILL_RETAIN_FLAG = 0x20
    WILL_FLAG = 0x04
    WILL_QOS_MASK = 0x18
    CLEAN_SESSION_FLAG = 0x02
    RESERVED_FLAG = 0x01

    def __init__(self, connect_flags: int = 0x00, keep_alive: int = 0, proto_name: str = "MQTT", proto_level: int = 0x04) -> None:
        super().__init__()
        self.proto_name = proto_name
        self.proto_level = proto_level
        self.flags = connect_flags
        self.keep_alive = keep_alive

    def __repr__(self) -> str:
        """Return a string representation of the ConnectVariableHeader object."""
        return (
            f"ConnectVariableHeader(proto_name={self.proto_name}, proto_level={self.proto_level},"
            f" flags={hex(self.flags)}, keepalive={self.keep_alive})"
        )

    def _set_flag(self, val: bool, mask: int) -> None:
        if val:
            self.flags |= mask
        else:
            self.flags &= ~mask

    def _get_flag(self, mask: int) -> bool:
        return bool(self.flags & mask)

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter, _: MQTTFixedHeader) -> Self:
        #  protocol name
        protocol_name = await decode_string(reader)

        # protocol level
        protocol_level_byte = await read_or_raise(reader, 1)
        protocol_level = bytes_to_int(protocol_level_byte)

        # flags
        flags_byte = await read_or_raise(reader, 1)
        flags = bytes_to_int(flags_byte)

        # keep-alive
        keep_alive_byte = await read_or_raise(reader, 2)
        keep_alive = bytes_to_int(keep_alive_byte)

        return cls(flags, keep_alive, protocol_name, protocol_level)

    def to_bytes(self) -> bytes | bytearray:
        out = bytearray()

        # Protocol name
        out.extend(encode_string(self.proto_name))
        # Protocol level
        out.append(self.proto_level)
        # flags
        out.append(self.flags)
        # keep alive
        out.extend(int_to_bytes(self.keep_alive, 2))

        return out

    @property
    def username_flag(self) -> bool:
        return self._get_flag(self.USERNAME_FLAG)

    @username_flag.setter
    def username_flag(self, val: bool) -> None:
        self._set_flag(val, self.USERNAME_FLAG)

    @property
    def password_flag(self) -> bool:
        return self._get_flag(self.PASSWORD_FLAG)

    @password_flag.setter
    def password_flag(self, val: bool) -> None:
        self._set_flag(val, self.PASSWORD_FLAG)

    @property
    def will_retain_flag(self) -> bool:
        return self._get_flag(self.WILL_RETAIN_FLAG)

    @will_retain_flag.setter
    def will_retain_flag(self, val: bool) -> None:
        self._set_flag(val, self.WILL_RETAIN_FLAG)

    @property
    def will_flag(self) -> bool:
        return self._get_flag(self.WILL_FLAG)

    @will_flag.setter
    def will_flag(self, val: bool) -> None:
        self._set_flag(val, self.WILL_FLAG)

    @property
    def clean_session_flag(self) -> bool:
        return self._get_flag(self.CLEAN_SESSION_FLAG)

    @clean_session_flag.setter
    def clean_session_flag(self, val: bool) -> None:
        self._set_flag(val, self.CLEAN_SESSION_FLAG)

    @property
    def reserved_flag(self) -> bool:
        return self._get_flag(self.RESERVED_FLAG)

    @reserved_flag.setter
    def reserved_flag(self, val: bool) -> None:
        self._set_flag(val, self.RESERVED_FLAG)

    @property
    def will_qos(self) -> int:
        return (self.flags & 0x18) >> 3

    @will_qos.setter
    def will_qos(self, val: int) -> None:
        self.flags &= 0xE7  # Reset QOS flags
        self.flags |= val << 3


class ConnectPayload(MQTTPayload[ConnectVariableHeader]):
    __slots__ = (
        "client_id",
        "client_id_is_random",
        "password",
        "username",
        "will_message",
        "will_topic",
    )

    def __init__(
        self,
        client_id: str | None = None,
        will_topic: str | None = None,
        will_message: bytes | bytearray | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        super().__init__()
        self.client_id_is_random = False
        self.client_id = client_id
        self.will_topic = will_topic
        self.will_message = will_message
        self.username = username
        self.password = password

    def __repr__(self) -> str:
        """Return a string representation of the ConnectPayload object."""
        return (
            f"ConnectVariableHeader(client_id={self.client_id}, will_topic={self.will_topic},"
            f"will_message={self.will_message!r}, username={self.username}, password={self.password})"
        )

    @classmethod
    async def from_stream(
        cls,
        reader: StreamReader | ReaderAdapter,
        _: MQTTFixedHeader | None,
        variable_header: ConnectVariableHeader | None,
    ) -> Self:
        payload = cls()
        #  Client identifier
        try:
            payload.client_id = await decode_string(reader)
        except NoDataError:
            payload.client_id = None

        if payload.client_id is None or payload.client_id == "":
            # A Server MAY allow a Client to supply a ClientId that has a length of zero bytes
            # [MQTT-3.1.3-6]
            payload.client_id = gen_client_id()
            # indicator to trow exception in case CLEAN_SESSION_FLAG is set to False
            payload.client_id_is_random = True

        # Read will topic, username and password
        if variable_header is not None and variable_header.will_flag:
            try:
                payload.will_topic = await decode_string(reader)
                payload.will_message = await decode_data_with_length(reader)
            except NoDataError:
                payload.will_topic = None
                payload.will_message = None

        if variable_header is not None and variable_header.username_flag:
            try:
                payload.username = await decode_string(reader)
            except NoDataError:
                payload.username = None

        if variable_header is not None and variable_header.password_flag:
            try:
                payload.password = await decode_string(reader)
            except NoDataError:
                payload.password = None

        return payload

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader | None = None,
        variable_header: ConnectVariableHeader | None = None,
    ) -> bytes | bytearray:
        out = bytearray()
        # Client identifier
        if self.client_id is not None:
            out.extend(encode_string(self.client_id))
        # Will topic / message
        if variable_header is not None and variable_header.will_flag:
            if self.will_topic is not None:
                out.extend(encode_string(self.will_topic))
            if self.will_message is not None:
                out.extend(encode_data_with_length(self.will_message))
        # username
        if variable_header is not None and variable_header.username_flag and self.username is not None:
            out.extend(encode_string(self.username))
        # password
        if variable_header is not None and variable_header.password_flag and self.password is not None:
            out.extend(encode_string(self.password))

        return out


class ConnectPacket(MQTTPacket[ConnectVariableHeader, ConnectPayload, MQTTFixedHeader]):  # type: ignore [type-var]
    VARIABLE_HEADER = ConnectVariableHeader
    PAYLOAD = ConnectPayload

    def __init__(
        self,
        fixed: MQTTFixedHeader | None = None,
        variable_header: ConnectVariableHeader | None = None,
        payload: ConnectPayload | None = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(CONNECT, 0x00)
        else:
            if fixed.packet_type is not CONNECT:
                msg = f"Invalid fixed packet type {fixed.packet_type} for ConnectPacket init"
                raise AMQTTError(msg)
            header = fixed
        super().__init__(header)
        self.variable_header = variable_header
        self.payload = payload

    @property
    def proto_name(self) -> str:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.proto_name

    @proto_name.setter
    def proto_name(self, name: str) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.proto_name = name

    @property
    def proto_level(self) -> int:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.proto_level

    @proto_level.setter
    def proto_level(self, level: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.proto_level = level

    @property
    def username_flag(self) -> bool:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.username_flag

    @username_flag.setter
    def username_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.username_flag = flag

    @property
    def password_flag(self) -> bool:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.password_flag

    @password_flag.setter
    def password_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.password_flag = flag

    @property
    def clean_session_flag(self) -> bool:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.clean_session_flag

    @clean_session_flag.setter
    def clean_session_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.clean_session_flag = flag

    @property
    def will_retain_flag(self) -> bool:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.will_retain_flag

    @will_retain_flag.setter
    def will_retain_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.will_retain_flag = flag

    @property
    def will_qos(self) -> int:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.will_qos

    @will_qos.setter
    def will_qos(self, flag: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.will_qos = flag

    @property
    def will_flag(self) -> bool:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.will_flag

    @will_flag.setter
    def will_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.will_flag = flag

    @property
    def reserved_flag(self) -> bool:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        return self.variable_header.reserved_flag

    @reserved_flag.setter
    def reserved_flag(self, flag: bool) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.reserved_flag = flag

    @property
    def client_id(self) -> str | None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.client_id

    @client_id.setter
    def client_id(self, client_id: str) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.client_id = client_id

    @property
    def client_id_is_random(self) -> bool:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.client_id_is_random

    @client_id_is_random.setter
    def client_id_is_random(self, client_id_is_random: bool) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.client_id_is_random = client_id_is_random

    @property
    def will_topic(self) -> str | None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.will_topic

    @will_topic.setter
    def will_topic(self, will_topic: str) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.will_topic = will_topic

    @property
    def will_message(self) -> bytes | bytearray | None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.will_message

    @will_message.setter
    def will_message(self, will_message: bytes | bytearray) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.will_message = will_message

    @property
    def username(self) -> str | None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.username

    @username.setter
    def username(self, username: str) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.username = username

    @property
    def password(self) -> str | None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.payload.password

    @password.setter
    def password(self, password: str) -> None:
        if self.payload is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        self.payload.password = password

    @property
    def keep_alive(self) -> int:
        if self.variable_header is None:
            msg = "Payload is not set"
            raise ValueError(msg)
        return self.variable_header.keep_alive

    @keep_alive.setter
    def keep_alive(self, keep_alive: int) -> None:
        if self.variable_header is None:
            msg = "Variable header is not set"
            raise ValueError(msg)
        self.variable_header.keep_alive = keep_alive
