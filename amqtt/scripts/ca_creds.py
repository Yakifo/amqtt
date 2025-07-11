import logging
from pathlib import Path
import sys

import typer

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, rich_markup_mode=None)


def main() -> None:
    """Generate a self-signed key and certificate for the broker."""
    app()

@app.command()
def ca_creds(
        country:str = typer.Option(..., "--country", help="x509 'country_name' attribute"),
        state:str = typer.Option(..., "--state", help="x509 'state_or_province_name' attribute"),
        locality:str = typer.Option(..., "--locality", help="x509 'locality_name' attribute"),
        org_name:str = typer.Option(..., "--org-name", help="x509 'organization_name' attribute"),
        cn: str = typer.Option(..., "--cn", help="x509 'common_name' attribute"),
        output_dir: str = typer.Option(Path('.').resolve().absolute(), "--output-dir", help="output directory"),
) -> None:
    """Generate a self-signed key and certificate for the broker."""
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    try:
        from amqtt.contrib.cert import generate_root_creds, write_key_and_crt  # pylint: disable=import-outside-toplevel
    except ImportError:
        msg = "Requires installation of the optional 'contrib' package: `pip install amqtt[contrib]`"
        logger.critical(msg)
        sys.exit(1)

    ca_key, ca_crt = generate_root_creds(country=country, state=state, locality=locality, org_name=org_name, cn=cn)

    write_key_and_crt(ca_key, ca_crt, 'ca', Path(output_dir))


if __name__ == "__main__":
    main()
