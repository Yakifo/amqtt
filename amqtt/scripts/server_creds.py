import logging
from pathlib import Path
import sys

import typer

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, rich_markup_mode=None)


def main() -> None:
    """Run the `server_creds` cli."""
    app()


@app.command()
def server_creds(
        country: str = typer.Option(..., "--country", help="x509 'country_name' attribute"),
        org_name: str = typer.Option(..., "--org-name", help="x509 'organization_name' attribute"),
        cn: str = typer.Option(..., "--cn", help="x509 'common_name' attribute"),
        output_dir: str = typer.Option(Path.cwd().absolute(), "--output-dir", help="output directory"),
        ca_key_fn: str = typer.Option("ca.key", "--ca-key", help="server key output filename."),
        ca_crt_fn: str = typer.Option("ca.crt", "--ca-crt", help="server cert output filename."),
) -> None:
    """Generate a key and certificate for the broker in pem format, signed by the provided CA credentials. With a key size of 2048 and a 1-year expiration."""  # noqa : E501
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    try:
        from amqtt.contrib.cert import (  # pylint: disable=import-outside-toplevel
            generate_server_csr,
            load_ca,
            sign_csr,
            write_key_and_crt,
        )
    except ImportError:
        msg = "Requires installation of the optional 'contrib' package: `pip install amqtt[contrib]`"
        logger.critical(msg)
        sys.exit(1)

    ca_key, ca_crt = load_ca(ca_key_fn, ca_crt_fn)

    server_key, server_csr = generate_server_csr(country=country, org_name=org_name, cn=cn)
    server_crt = sign_csr(server_csr, ca_key, ca_crt)

    write_key_and_crt(server_key, server_crt, "server", Path(output_dir))


if __name__ == "__main__":
    main()
