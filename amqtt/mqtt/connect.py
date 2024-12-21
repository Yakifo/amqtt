# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

from amqtt.adapters import ReaderAdapter
from amqtt.codecs import (
    bytes_to_int,
    decode_data_with_length,
    decode_string,
    encode_data_with_length,
    encode_string,
    int_to_bytes,
    read_or_raise,
)
from amqtt.errors import AMQTTException, NoDataException
from amqtt.mqtt.packet import (
    CONNECT,
    MQTTFixedHeader,
    MQTTPacket,
    MQTTPayload,
    MQTTVariableHeader,
)
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

    def __init__(
        self,
        connect_flags=0x00,
        keep_alive=0,
        proto_name="MQTT",
        proto_level=0x04,
    ) -> None:
        super().__init__()
        self.proto_name = proto_name
        self.proto_level = proto_level
        self.flags = connect_flags
        self.keep_alive = keep_alive

    def __repr__(self) -> str:
        return f"ConnectVariableHeader(proto_name={self.proto_name}, proto_level={self.proto_level}, flags={hex(self.flags)}, keepalive={self.keep_alive})"

    def _set_flag(self, val, mask) -> None:
        if val:
            self.flags |= mask
        else:
            self.flags &= ~mask

    def _get_flag(self, mask) -> bool:
        return bool(self.flags & mask)

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

    @property
    def will_qos(self):
        return (self.flags & 0x18) >> 3

    @will_qos.setter
    def will_qos(self, val: int) -> None:
        self.flags &= 0xE7  # Reset QOS flags
        self.flags |= val << 3

    @classmethod
    async def from_stream(cls, reader: ReaderAdapter, fixed_header: MQTTFixedHeader):
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

    def to_bytes(self):
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


class ConnectPayload(MQTTPayload):
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
        client_id=None,
        will_topic=None,
        will_message=None,
        username=None,
        password=None,
    ) -> None:
        super().__init__()
        self.client_id_is_random = False
        self.client_id = client_id
        self.will_topic = will_topic
        self.will_message = will_message
        self.username = username
        self.password = password

    def __repr__(self) -> str:
        return f"ConnectVariableHeader(client_id={self.client_id}, will_topic={self.will_topic}, will_message={self.will_message}, username={self.username}, password={self.password})"

    @classmethod
    async def from_stream(
        cls,
        reader: ReaderAdapter,
        fixed_header: MQTTFixedHeader,
        variable_header: ConnectVariableHeader,
    ):
        payload = cls()
        #  Client identifier
        try:
            payload.client_id = await decode_string(reader)
        except NoDataException:
            payload.client_id = None

        if payload.client_id is None or payload.client_id == "":
            # A Server MAY allow a Client to supply a ClientId that has a length of zero bytes
            # [MQTT-3.1.3-6]
            payload.client_id = gen_client_id()
            # indicator to trow exception in case CLEAN_SESSION_FLAG is set to False
            payload.client_id_is_random = True

        # Read will topic, username and password
        if variable_header.will_flag:
            try:
                payload.will_topic = await decode_string(reader)
                payload.will_message = await decode_data_with_length(reader)
            except NoDataException:
                payload.will_topic = None
                payload.will_message = None

        if variable_header.username_flag:
            try:
                payload.username = await decode_string(reader)
            except NoDataException:
                payload.username = None

        if variable_header.password_flag:
            try:
                payload.password = await decode_string(reader)
            except NoDataException:
                payload.password = None

        return payload

    def to_bytes(
        self,
        fixed_header: MQTTFixedHeader,
        variable_header: ConnectVariableHeader,
    ):
        out = bytearray()
        # Client identifier
        out.extend(encode_string(self.client_id))
        # Will topic / message
        if variable_header.will_flag:
            out.extend(encode_string(self.will_topic))
            out.extend(encode_data_with_length(self.will_message))
        # username
        if variable_header.username_flag:
            out.extend(encode_string(self.username))
        # password
        if variable_header.password_flag:
            out.extend(encode_string(self.password))

        return out


class ConnectPacket(MQTTPacket):
    VARIABLE_HEADER = ConnectVariableHeader
    PAYLOAD = ConnectPayload

    @property
    def proto_name(self):
        return self.variable_header.proto_name

    @proto_name.setter
    def proto_name(self, name: str) -> None:
        self.variable_header.proto_name = name

    @property
    def proto_level(self):
        return self.variable_header.proto_level

    @proto_level.setter
    def proto_level(self, level) -> None:
        self.variable_header.proto_level = level

    @property
    def username_flag(self):
        return self.variable_header.username_flag

    @username_flag.setter
    def username_flag(self, flag) -> None:
        self.variable_header.username_flag = flag

    @property
    def password_flag(self):
        return self.variable_header.password_flag

    @password_flag.setter
    def password_flag(self, flag) -> None:
        self.variable_header.password_flag = flag

    @property
    def clean_session_flag(self):
        return self.variable_header.clean_session_flag

    @clean_session_flag.setter
    def clean_session_flag(self, flag) -> None:
        self.variable_header.clean_session_flag = flag

    @property
    def will_retain_flag(self):
        return self.variable_header.will_retain_flag

    @will_retain_flag.setter
    def will_retain_flag(self, flag) -> None:
        self.variable_header.will_retain_flag = flag

    @property
    def will_qos(self):
        return self.variable_header.will_qos

    @will_qos.setter
    def will_qos(self, flag) -> None:
        self.variable_header.will_qos = flag

    @property
    def will_flag(self):
        return self.variable_header.will_flag

    @will_flag.setter
    def will_flag(self, flag) -> None:
        self.variable_header.will_flag = flag

    @property
    def reserved_flag(self):
        return self.variable_header.reserved_flag

    @reserved_flag.setter
    def reserved_flag(self, flag) -> None:
        self.variable_header.reserved_flag = flag

    @property
    def client_id(self):
        return self.payload.client_id

    @client_id.setter
    def client_id(self, client_id) -> None:
        self.payload.client_id = client_id

    @property
    def client_id_is_random(self) -> bool:
        return self.payload.client_id_is_random

    @client_id_is_random.setter
    def client_id_is_random(self, client_id_is_random: bool) -> None:
        self.payload.client_id_is_random = client_id_is_random

    @property
    def will_topic(self):
        return self.payload.will_topic

    @will_topic.setter
    def will_topic(self, will_topic) -> None:
        self.payload.will_topic = will_topic

    @property
    def will_message(self):
        return self.payload.will_message

    @will_message.setter
    def will_message(self, will_message) -> None:
        self.payload.will_message = will_message

    @property
    def username(self):
        return self.payload.username

    @username.setter
    def username(self, username) -> None:
        self.payload.username = username

    @property
    def password(self):
        return self.payload.password

    @password.setter
    def password(self, password) -> None:
        self.payload.password = password

    @property
    def keep_alive(self):
        return self.variable_header.keep_alive

    @keep_alive.setter
    def keep_alive(self, keep_alive) -> None:
        self.variable_header.keep_alive = keep_alive

    def __init__(
        self,
        fixed: MQTTFixedHeader = None,
        vh: ConnectVariableHeader = None,
        payload: ConnectPayload = None,
    ) -> None:
        if fixed is None:
            header = MQTTFixedHeader(CONNECT, 0x00)
        else:
            if fixed.packet_type is not CONNECT:
                msg = f"Invalid fixed packet type {fixed.packet_type} for ConnectPacket init"
                raise AMQTTException(
                    msg,
                )
            header = fixed
        super().__init__(header)
        self.variable_header = vh
        self.payload = payload
