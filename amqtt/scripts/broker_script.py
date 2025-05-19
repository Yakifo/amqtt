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

from amqtt import __version__ as amqtt_version
from amqtt.broker import Broker
from amqtt.utils import read_yaml_config

default_config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
        },
    },
    "sys_interval": 10,
    "auth": {
        "allow-anonymous": True,
        "password-file": Path(__file__).parent / "passwd",
        "plugins": ["auth_file", "auth_anonymous"],
    },
    "topic-check": {"enabled": False},
}

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the MQTT broker."""
    typer.run(broker_main)


def _version(v:bool) -> None:
    if v:
        typer.echo(f"{amqtt_version}")
        raise typer.Exit(code=0)


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

    if config_file:
        config = read_yaml_config(config_file)
    else:
        config = read_yaml_config(Path(__file__).parent / "default_broker.yaml")
        logger.debug("Using default configuration")

    loop = asyncio.get_event_loop()
    broker = Broker(config)
    try:
        loop.run_until_complete(broker.start())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(broker.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
