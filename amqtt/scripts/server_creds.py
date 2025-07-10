import logging
from pathlib import Path
import sys

from cryptography.hazmat.primitives import serialization
import typer

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, rich_markup_mode=None)


def main() -> None:
    """Generate a self-signed key and certificate for the broker."""
    app()

@app.command()
def server_creds(
        country:str = typer.Option(..., "--country", help="x509 'country_name' attribute"),
        state:str = typer.Option(..., "--state", help="x509 'state_or_province_name' attribute"),
        locality:str = typer.Option(..., "--locality", help="x509 'locality_name' attribute"),
        org_name:str = typer.Option(..., "--org-name", help="x509 'organization_name' attribute"),
        cn: str = typer.Option(..., "--cn", help="x509 'common_name' attribute"),
        server_key:str = typer.Option("ca.key", "--server-key", help="server key output filename."),
        server_crt:str = typer.Option("ca.crt", "--server-crt", help="server cert output filename."),
) -> None:
    """Generate a self-signed key and certificate for the broker."""
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    try:
        from amqtt.contrib.cert import generate_server_creds  # pylint: disable=import-outside-toplevel
    except ImportError:
        msg = "Requires installation of the optional 'contrib' package: `pip install amqtt[contrib]`"
        logger.critical(msg)
        sys.exit(1)

    key, cert = generate_server_creds(country, state, locality, org_name, cn)

    with Path(server_key).open("wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,  # or PKCS8
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with Path(server_crt).open("wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

if __name__ == "__main__":
    main()
