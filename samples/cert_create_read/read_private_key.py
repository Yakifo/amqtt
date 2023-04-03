from cryptography.hazmat.primitives import serialization
from read_existing_cert_example import read_cert
from OpenSSL import crypto, SSL
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

with open("private_1.key", "rb") as key_file:
    private_key = serialization.load_pem_private_key(
        key_file.read(),
        password=None,
    )
   
   
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.BestAvailableEncryption(b"passphrase"),
)
pem.splitlines()[0]
b'-----BEGIN PRIVATE KEY-----'
print(pem)

x509 = read_cert("selfsigned_example_1.crt")
pubkeyobj = x509.get_pubkey()
pubkeystr = crypto.dump_publickey(crypto.FILETYPE_PEM, pubkeyobj)


# Encrypt
ciphertext = pubkeyobj.encrypt(
    "hey",
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA1()),
        algorithm=hashes.SHA1(),
        label=None
    )
)

plaintext = private_key.decrypt(
    ciphertext,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA1()),
        algorithm=hashes.SHA1(),
        label=None
    )
)

print(plaintext)
