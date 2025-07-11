import logging
from pathlib import Path
import sys

import typer

logger = logging.getLogger(__name__)


app = typer.Typer(add_completion=False, rich_markup_mode=None)


def main() -> None:
    """Generate a signed certificate and key for device."""
    app()


@app.command()
def device_creds( # pylint: disable=too-many-locals
        country: str = typer.Option(..., "--country", help="x509 'country_name' attribute"),
        org_name: str = typer.Option(..., "--org-name", help="x509 'organization_name' attribute"),
        device_id: str = typer.Option(..., "--device-id", help="device id for the SAN"),
        uri: str = typer.Option(..., "--uri", help="domain name for device SAN"),
        output_dir: str = typer.Option(Path().resolve().absolute(), "--output-dir", help="output directory"),
        ca_key_fn: str = typer.Option("ca.key", "--ca-key", help="root key filename used for signing."),
        ca_crt_fn: str = typer.Option("ca.crt", "--ca-crt", help="root cert filename used for signing."),
) -> None:
    """Generate a signed certificate and key for device."""
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    try:
        from amqtt.contrib.cert import (  # pylint: disable=import-outside-toplevel
            generate_device_csr,
            load_ca,
            sign_csr,
            write_key_and_crt,
        )
    except ImportError:
        msg = "Requires installation of the optional 'contrib' package: `pip install amqtt[contrib]`"
        logger.critical(msg)
        sys.exit(1)

    ca_key, ca_crt = load_ca(ca_key_fn, ca_crt_fn)

    uri_san = f"spiffe://{uri}/device/{device_id}"
    dns_san = f"{device_id}.local"

    device_key, device_csr = generate_device_csr(
        country=country,
        org_name=org_name,
        common_name=device_id,
        uri_san=uri_san,
        dns_san=dns_san
    )

    device_crt = sign_csr(device_csr, ca_key, ca_crt)

    write_key_and_crt(device_key, device_crt, device_id, Path(output_dir))

    logger.info(f"✅ Created: {device_id}.crt and {device_id}.key")

if __name__ == "__main__":
    main()
