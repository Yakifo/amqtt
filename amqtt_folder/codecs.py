# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
import asyncio
from struct import pack, unpack
from amqtt_folder.errors import NoDataException


def bytes_to_hex_str(data):
    """
    converts a sequence of bytes into its displayable hex representation, ie: 0x??????
    :param data: byte sequence
    :return: Hexadecimal displayable representation
    """
    return "0x" + "".join(format(b, "02x") for b in data)
"""
Burcu: the 02 means it will pad with up to 2 leading 0s if necessary. 
This is important since [0x1, 0x1, 0x1] i.e. (0x010101) would be formatted to "111" instead of "010101"
"""



def bytes_to_int(data):
    """
    convert a sequence of bytes to an integer using big endian byte ordering
    :param data: byte sequence
    :return: integer value
    """
    try:
        return int.from_bytes(data, byteorder="big")
    except:
        return data
 


def int_to_bytes(int_value: int, length: int = None) -> bytes:
    """
    convert an integer to a sequence of bytes using big endian byte ordering
    :param int_value: integer value to convert
    :param length: (optional) byte length
    :return: byte sequence
    """
    if length == 1:
        fmt = "!B"
    elif length == 2:
        fmt = "!H"
    else: 
        fmt = "!B"
    return pack(fmt, int_value)

"""
Burcu:
    struct.pack(format, v1, v2, ...)
    Return a bytes object containing the values v1, v2, … packed according to the format string format. 
    The arguments must match the values required by the format exactly.

    struct.pack takes non-byte values (e.g. integers, strings, etc.) and converts them to bytes. 
    And conversely, struct.unpack takes bytes and converts them to their 'higher-order' equivalents.
"""





async def read_or_raise(reader, n=-1):
    """
    Read a given byte number from Stream. NoDataException is raised if read gives no data
    :param reader: reader adapter
    :param n: number of bytes to read
    :return: bytes read
    """
    try:
        data = await reader.read(n)
    except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
        data = None
    if not data:
        raise NoDataException("No more data")
    return data


async def decode_string(reader) -> str:     #Burcu: string return ediyor
    """
    Read a string from a reader and decode it according to MQTT string specification
    :param reader: Stream reader
    :return: string read from stream
    """
    length_bytes = await read_or_raise(reader, 2)
    str_length = unpack("!H", length_bytes)
    if str_length[0]: 
        byte_str = await read_or_raise(reader, str_length[0])
        try:
            return byte_str.decode(encoding="utf-8")
        except:
            return str(byte_str)
    else:
        return ""


async def decode_data_with_length(reader) -> bytes:     #Burcu: byte return ediyor
    """
    Read data from a reader. Data is prefixed with 2 bytes length
    :param reader: Stream reader
    :return: bytes read from stream (without length)
    """
    length_bytes = await read_or_raise(reader, 2)
    bytes_length = unpack("!H", length_bytes)       #Burcu: 2 byte alıp unsigned short integera çeviriyor
    data = await read_or_raise(reader, bytes_length[0])
    return data


def encode_string(string: str) -> bytes:   
#Burcu: input string formatında, onu byte'a çevirip başına length ekleyip return ediyor    
    data = string.encode(encoding="utf-8")
    data_length = len(data)
    return int_to_bytes(data_length, 2) + data


def encode_data_with_length(data: bytes) -> bytes:
#Burcu: input byte formatında, başına length ekleyip return ediyor
    data_length = len(data)
    return int_to_bytes(data_length, 2) + data


async def decode_packet_id(reader) -> int:
    """
    Read a packet ID as 2-bytes int from stream according to MQTT specification (3.3.1)
    :param reader: Stream reader
    :return: Packet ID
    """
    packet_id_bytes = await read_or_raise(reader, 2)
    packet_id = unpack("!H", packet_id_bytes)
    return packet_id[0]


def int_to_bytes_str(value: int) -> bytes:
    """
    Converts a int value to a bytes array containing the numeric character.
    Ex: 123 -> b'123'
    :param value: int value to convert
    :return: bytes array
    """
    return str(value).encode("utf-8")


