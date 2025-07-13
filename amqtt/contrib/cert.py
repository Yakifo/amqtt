from dataclasses import dataclass
from datetime import datetime, timedelta

try:
    from datetime import UTC
except ImportError:
    # support for python 3.10
    from datetime import timezone
    UTC = timezone.utc


from ipaddress import IPv4Address
import logging
from pathlib import Path
import re

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import Certificate, CertificateSigningRequest
from cryptography.x509.oid import NameOID

from amqtt.plugins.base import BaseAuthPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


class CertificateAuthPlugin(BaseAuthPlugin):

    async def authenticate(self, *, session: Session) -> bool | None:

        if not session.ssl_object:
            return False

        der_cert = session.ssl_object.getpeercert(binary_form=True)
        if der_cert:
            cert = x509.load_der_x509_certificate(der_cert, backend=default_backend())

            try:
                san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                uris = san.value.get_values_for_type(x509.UniformResourceIdentifier)

                if self.config.uri_domain not in uris[0]:
                    return False

                pattern = rf"^spiffe://{re.escape(self.config.uri_domain)}/device/([^/]+)$"
                match = re.match(pattern, uris[0])
                if not match:
                    return False

                return match.group(1) == session.client_id

            except x509.ExtensionNotFound:
                logger.warning("No SAN extension found.")

        return False

    @dataclass
    class Config:
        """Configuration for the CertificateAuthPlugin.

        Members:
            - uri_domain *(str)* the domain that is expected as part of the device certificate's spiffe

        """

        uri_domain: str

def generate_root_creds(country:str, state:str, locality:str,
                          org_name:str, cn: str) -> tuple[rsa.RSAPrivateKey, Certificate]:
    """Generate CA key and certificate."""
    # generate private key for the server
    ca_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )
    # Create certificate subject and issuer (self-signed)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name),
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ])

    # 3. Build self-signed certificate
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=3650))  # 10 years
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=False,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    return ca_key, cert


def generate_server_csr(country:str, org_name: str, cn:str) -> tuple[rsa.RSAPrivateKey, CertificateSigningRequest]:
    """Generate server private key and server certificate-signing-request."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(cn),
                x509.IPAddress(IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    return key, csr



def generate_device_csr(country: str, org_name: str, common_name: str,
                        uri_san: str, dns_san: str
                        ) -> tuple[rsa.RSAPrivateKey, CertificateSigningRequest]:
    """Generate a device key and a csr."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org_name
                               ),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.UniformResourceIdentifier(uri_san),
                x509.DNSName(dns_san),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    return key, csr

def sign_csr(csr: CertificateSigningRequest,
             ca_key: rsa.RSAPrivateKey,
             ca_cert: Certificate, validity_days: int=365) -> Certificate:
    """Sign a csr with CA credentials."""
    return (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=validity_days))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value,
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()),  # type: ignore[arg-type]
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

def load_ca(ca_key_fn:str, ca_crt_fn:str) -> tuple[rsa.RSAPrivateKey, Certificate]:
    """Load server key and certificate."""
    with Path(ca_key_fn).open("rb") as f:
        ca_key: rsa.RSAPrivateKey = serialization.load_pem_private_key(f.read(), password=None)  # type: ignore[assignment]
    with Path(ca_crt_fn).open("rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    return ca_key, ca_cert


def write_key_and_crt(key:rsa.RSAPrivateKey, crt:Certificate,
                      prefix:str, path: Path | None = None) -> None:
    """Create pem-encoded files for key and certificate."""
    path = path or Path()

    crt_fn = path / f"{prefix}.crt"
    key_fn = path / f"{prefix}.key"

    with crt_fn.open("wb") as f:
        f.write(crt.public_bytes(serialization.Encoding.PEM))
    with key_fn.open("wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))
