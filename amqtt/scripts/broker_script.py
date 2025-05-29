"""aMQTT - MQTT 3.1.1 broker.

Usage:
    amqtt --version
    amqtt (-h | --help)
    amqtt [-c <config_file> ] [-d]

Options:
    -h --help           Show this screen.
    --version           Show version.
    -c <config_file>    Broker configuration file (YAML format)
    -d                  Enable debug messages
"""

import asyncio
import logging
from pathlib import Path

import typer
from yaml.parser import ParserError

from amqtt import __version__ as amqtt_version
from amqtt.broker import Broker
from amqtt.errors import BrokerError
from amqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


app = typer.Typer(rich_markup_mode=None)


def main() -> None:
    """Run the MQTT broker."""
    app()


def _version(v:bool) -> None:
    if v:
        typer.echo(f"{amqtt_version}")
        raise typer.Exit(code=0)


@app.command()
def broker_main(
        config_file: str | None = typer.Option(None, "-c", help="Broker configuration file (YAML format)"),
        debug: bool = typer.Option(False, "-d", help="Enable debug messages"),
        version: bool = typer.Option(  # noqa : ARG001
            False,
            "--version",
            callback=_version,
            is_eager=True,
            help="Show version and exit",
        ),
) -> None:
    """Run the MQTT broker."""
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"

    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format=formatter)
    try:
        if config_file:
            config = read_yaml_config(config_file)
        else:
            config = read_yaml_config(Path(__file__).parent / "default_broker.yaml")
            logger.debug("Using default configuration")
    except FileNotFoundError as exc:
        typer.echo(f"❌ Config file error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


    loop = asyncio.get_event_loop()
    try:
        broker = Broker(config)
    except (BrokerError, ParserError) as exc:
        typer.echo(f"❌ Broker failed to start: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        loop.run_until_complete(broker.start())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(broker.shutdown())
    except Exception as exc:
        typer.echo("❌ Connection failed", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        loop.close()


if __name__ == "__main__":
    main()
