import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as padding2
from cryptography.hazmat.backends import default_backend
from django.utils.encoding import force_bytes
import secrets

key2048 = b'\x99\xbb\xb7PZ6\xac\xa6fLL\xa9j\xcc#\xef\xfe\xa1p\xc4G\xe4\xe27\x161\xfa\xc97 \x0b x\x10\xc9_\x88}y&\x04b\xd1\x12\xee\xc0\xe0D\xa9\xc1b|\x87\xec\xb4\xb1\x88\xd8\xf66\xd5s\x02\xe5\xe5\x13\x9f\xffI^Lc(\x1b\x82\xac\xe1p\xbb1\xb4C\x9c\x8e\x19\x9a\xf3?\xd3}\xcb\x87\xc0O\xcf\x8e\x8e(\xa5\xa1\x11\x91\x16XT\x82\xee\x82N\xb5F\x12\x07\x89\xe9\x03\x974\x8e\xe6DW\x97$\x80"~|\xea^\x08\xab\x07\x7f>\\\'z\x1c\xc1\x9e\x8fL\xa8\xd3Cu\x8bYg5\xa0\xe0>\xea\xfb#\xe835\x92\xc0\x9e!\xac\xa1\xc7\x03\x1f\x86k$\xdbi\xe3\x00\xdb\x03Q\x0c+?\xb6\x87\xb0X{q\xcf\xee\xb1\xe0\x1e\xd4\xd4\x96\xc3o\xea\xdbq\xc2\xe5>\xc8\xf9m\xc8\xbc\xab\xad\xb8\xad\x08P\xc9s\xa8:[j\x16/\x9a\xc7a\xd4*m\x80V\x0b\xec+E)\x8aV\xef^F(X0Ro\xec4I\xa7\xe7\xed\xda\x1f\xb0/'

"""
info = b"hkdf-example"
hkdf = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,
    info=info,
)

hkdf2 = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,
    info=info,
)
key = hkdf.derive(key2048)
key2 = hkdf2.derive(key2048)
print(key2048)
print(key)
print(key2)

hkdf = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,
    info=info,
)
hkdf.verify(key2048, key)
"""
"""
iv = os.urandom(16)
cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
encryptor = cipher.encryptor()
ct = encryptor.update(b"a secret message") + encryptor.finalize()
decryptor = cipher.decryptor()
decryptor.update(ct) + decryptor.finalize()
b'a secret message'
print(encryptor)
print(decryptor)
"""






value = force_bytes("12345678901234567890")

backend = default_backend()
key = force_bytes(base64.urlsafe_b64encode(force_bytes(key2048))[:32])
key2 = force_bytes(base64.urlsafe_b64encode(force_bytes(key2048))[:32])
print(key)
print(key2)
encryptor = Cipher(algorithms.AES(key), modes.ECB(), backend).encryptor()
decryptor = Cipher(algorithms.AES(key), modes.ECB(), backend).decryptor()


padder = padding2.PKCS7(algorithms.AES(key).block_size).padder()
padded_data = padder.update(value) + padder.finalize()
encrypted_text = encryptor.update(padded_data) + encryptor.finalize()
print(encrypted_text)

padder = padding2.PKCS7(algorithms.AES(key).block_size).unpadder()
decrypted_data = decryptor.update(encrypted_text) 
unpadded = padder.update(decrypted_data) + padder.finalize()
print(unpadded)





nonce = secrets.token_urlsafe()
value_str = nonce + "::::" + "123456"
value = force_bytes(value_str)
sessionkey = force_bytes(base64.urlsafe_b64encode(force_bytes(key2048))[:32])
backend = default_backend()
encryptor = Cipher(algorithms.AES(sessionkey), modes.ECB(), backend).encryptor()
padder = padding2.PKCS7(algorithms.AES(sessionkey).block_size).padder()
padded_data = padder.update(value) + padder.finalize()
encrypted_text = encryptor.update(padded_data) + encryptor.finalize()
print(encrypted_text)