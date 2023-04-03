from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import utils
from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.backends import default_backend


with open("key.pem", "rb") as key_file:
    private_key = serialization.load_pem_private_key(
        key_file.read(),
        password= None,
    )

pem = private_key.private_bytes(
   encoding=serialization.Encoding.PEM,
   format=serialization.PrivateFormat.TraditionalOpenSSL,
   encryption_algorithm=serialization.NoEncryption()
)
pem.splitlines()[0]
b'-----BEGIN ENCRYPTED PRIVATE KEY-----'
print(pem)




public_key = private_key.public_key()
pem = public_key.public_bytes(
   encoding=serialization.Encoding.PEM,
   format=serialization.PublicFormat.SubjectPublicKeyInfo
)
pem.splitlines()[0]
b'-----BEGIN PUBLIC KEY-----'
print(pem)

message = b"A message I want to sign"
signature = private_key.sign(
    message,
    padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.MAX_LENGTH
    ),
    hashes.SHA256()
)


public_key = private_key.public_key()
try:
   
    x = private_key.verify(
                    signature,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
    print("####", x)
except:
    print("not verified")

message = b"encrypted data"
ciphertext = public_key.encrypt(
    message,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    )
)

plaintext = private_key.decrypt(
    ciphertext,
    padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    )
)
print(plaintext)





with open("certificate.pem", "rb") as key_file:
    x509 = load_pem_x509_certificate(
        key_file.read()  
    )

public_key = x509.public_key()
pem = public_key.public_bytes(
   encoding=serialization.Encoding.PEM,
   format=serialization.PublicFormat.SubjectPublicKeyInfo
)

b'-----BEGIN PUBLIC KEY-----'
print(pem)


pem = x509.public_bytes(
   encoding=serialization.Encoding.PEM
)
print(pem)