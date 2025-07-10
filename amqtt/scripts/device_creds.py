import logging
from pathlib import Path
import sys

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import Certificate
import typer

logger = logging.getLogger(__name__)


app = typer.Typer(add_completion=False, rich_markup_mode=None)


def main() -> None:
    """Generate a signed certificate and key for device."""
    app()

def load_ca(server_key:str, server_crt:str) -> tuple[rsa.RSAPrivateKey, Certificate]:
    """Load server key and certificate."""
    with Path(server_key).open("rb") as f:
        ca_key: rsa.RSAPrivateKey = serialization.load_pem_private_key(f.read(), password=None)  # type: ignore[assignment]
    with Path(server_crt).open("rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    return ca_key, ca_cert


@app.command()
def device_creds( # pylint: disable=too-many-locals
        country: str = typer.Option(..., "--country", help="x509 'country_name' attribute"),
        org_name: str = typer.Option(..., "--org-name", help="x509 'organization_name' attribute"),
        device_id: str = typer.Option(..., "--device-id", help="device id for the SAN"),
        uri: str = typer.Option(..., "--uri", help="domain name for device SAN"),
        output_dir: str = typer.Option(Path(__file__).parent.absolute(), "--output-dir", help="output directory"),
        server_key: str = typer.Option("ca.key", "--server-key", help="server key filename used for signing."),
        server_crt: str = typer.Option("ca.crt", "--server-crt", help="server cert filename used for signing."),
) -> None:
    """Generate a signed certificate and key for device."""
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    try:
        from amqtt.contrib.cert import generate_device_csr, sign_device_csr  # pylint: disable=import-outside-toplevel
    except ImportError:
        msg = "Requires installation of the optional 'contrib' package: `pip install amqtt[contrib]`"
        logger.critical(msg)
        sys.exit(1)

    ca_key, ca_cert = load_ca(server_key, server_crt)

    uri_san = f"spiffe://{uri}/device/{device_id}"
    dns_san = f"{device_id}.local"

    device_key, device_csr = generate_device_csr(
        country=country,
        org_name=org_name,
        common_name=device_id,
        uri_san=uri_san,
        dns_san=dns_san
    )

    device_cert = sign_device_csr(device_csr, ca_key, ca_cert)

    device_crt_fn = Path(output_dir) / f"{device_id}.crt"
    device_key_fn = Path(output_dir) / f"{device_id}.key"

    with device_crt_fn.open("wb") as f:
        f.write(device_cert.public_bytes(serialization.Encoding.PEM))
    with device_key_fn.open("wb") as f:
        f.write(device_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    logger.info(f"✅ Created: {device_id}.crt and {device_id}.key")

if __name__ == "__main__":
    main()
