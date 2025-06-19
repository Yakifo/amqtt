import asyncio
from struct import pack, unpack

from amqtt.adapters import ReaderAdapter
from amqtt.errors import NoDataError, ZeroLengthReadError


def bytes_to_hex_str(data: bytes | bytearray) -> str:
    """Convert a sequence of bytes into its displayable hex representation, ie: 0x??????.

    :param data: byte sequence
    :return: Hexadecimal displayable representation.
    """
    return "0x" + "".join(format(b, "02x") for b in data)


def bytes_to_int(data: bytes | int) -> int:
    """Convert a sequence of bytes to an integer using big endian byte ordering.

    :param data: byte sequence
    :return: integer value.
    """
    if isinstance(data, int):
        return data

    return int.from_bytes(data, byteorder="big")


def int_to_bytes(int_value: int, length: int) -> bytes:
    """Convert an integer to a sequence of bytes using big endian byte ordering.

    :param int_value: integer value to convert
    :param length: byte length (must be 1 or 2)
    :return: byte sequence
    :raises ValueError: if the length is unsupported
    """
    # Map length to the appropriate format string
    fmt_mapping = {
        1: "!B",  # 1 byte, unsigned char
        2: "!H",  # 2 bytes, unsigned short
    }

    fmt = fmt_mapping.get(length)
    if not fmt:
        msg = "Unsupported length for int to bytes conversion. Only lengths 1 or 2 are allowed."
        raise ValueError(msg)

    return pack(fmt, int_value)


async def read_or_raise(reader: ReaderAdapter | asyncio.StreamReader, n: int = -1) -> bytes:
    """Read a given byte number from Stream. NoDataException is raised if read gives no data.

    :param reader: reader adapter
    :param n: number of bytes to read
    :return: bytes read.
    """
    try:
        data = await reader.read(n)
    except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
        data = None
    if data is None:
        msg = "No more data"
        raise NoDataError(msg)
    return data


async def decode_string(reader: ReaderAdapter | asyncio.StreamReader) -> str:
    """Read a string from a reader and decode it according to MQTT string specification.

    :param reader: Stream reader
    :return: string read from stream.
    """
    length_bytes = await read_or_raise(reader, 2)
    if len(length_bytes) < 1:
        raise ZeroLengthReadError
    str_length = unpack("!H", length_bytes)[0]
    if str_length:
        byte_str = await read_or_raise(reader, str_length)
        try:
            return byte_str.decode(encoding="utf-8")
        except UnicodeDecodeError:
            return str(byte_str)
    else:
        return ""


async def decode_data_with_length(reader: ReaderAdapter | asyncio.StreamReader) -> bytes:
    """Read data from a reader. Data is prefixed with 2 bytes length.

    :param reader: Stream reader
    :return: bytes read from stream (without length).
    """
    length_bytes = await read_or_raise(reader, 2)
    if len(length_bytes) < 1:
        raise ZeroLengthReadError
    bytes_length = unpack("!H", length_bytes)[0]
    return await read_or_raise(reader, bytes_length)


def encode_string(string: str) -> bytes:
    """Encode a string with its length as prefix.

    :param string: string to encode
    :return: string with length prefix.
    """
    data = string.encode(encoding="utf-8")
    data_length = len(data)
    return int_to_bytes(data_length, 2) + data


def encode_data_with_length(data: bytes | bytearray) -> bytes:
    """Encode data with its length as prefix.

    :param data: data to encode
    :return: data with length prefix.
    """
    data_length = len(data)
    return int_to_bytes(data_length, 2) + data


async def decode_packet_id(reader: ReaderAdapter | asyncio.StreamReader) -> int:
    """Read a packet ID as 2-bytes int from stream according to MQTT specification (2.3.1).

    :param reader: Stream reader
    :return: Packet ID.
    """
    packet_id_bytes = await read_or_raise(reader, 2)
    packet_id = unpack("!H", packet_id_bytes)
    packet: int = packet_id[0]
    return packet


def int_to_bytes_str(value: int) -> bytes:
    """Convert an int value to a bytes array containing the numeric character.

    Ex: 123 -> b'123'
    :param value: int value to convert
    :return: bytes array.
    """
    return str(value).encode("utf-8")
