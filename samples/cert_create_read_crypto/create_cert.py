from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime




key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
# Write our key to disk for safe keeping
with open("key.pem", "wb") as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))


# Various details about who we are. For a self-signed certificate the
# subject and issuer are always the same.
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"TR"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"IST"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"IST"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Sabanci Univ"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"amqtt_broker"),
])
cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.datetime.utcnow()
).not_valid_after(
    # Our certificate will be valid for 10 days
    datetime.datetime.utcnow() + datetime.timedelta(days=100)
).add_extension(
    x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
    critical=False,
# Sign our certificate with our private key
).sign(key, hashes.SHA256())
# Write our certificate out to disk.
with open("certificate.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))