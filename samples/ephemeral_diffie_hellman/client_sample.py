import socket
import amqtt.codecs as codecs

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 65431  # The port used by the server

CONNECT_FLAG = 16

#print(b"Hello, world")
#print(codecs.int_to_bytes(16, 1))



'''bytesarray = bytearray(codecs.int_to_bytes(16, 1))

bytesarray.append(1)
bytesarray.append(1)

print(bytesarray)
print(codecs.bytes_to_hex_str(bytesarray))'''



with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print(b"Hello, world")
    s.sendall(b"Hello, world")
    s.sendall(b"Hello, world denemeeeeeee")
    s.sendall(b"Hello, world 2")
    data = s.recv(1024)

print(f"Received {data!r}")

def send_connect():
    bytes_to_send = bytearray()

    bytes_to_send.extend(codecs.int_to_bytes(CONNECT_FLAG))



