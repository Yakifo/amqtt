import asyncio
import logging
from pathlib import Path

import typer
from yaml.parser import ParserError

from amqtt import __version__ as amqtt_version
from amqtt.broker import Broker
from amqtt.errors import BrokerError, PluginError
from amqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


app = typer.Typer(add_completion=False, rich_markup_mode=None)


def main() -> None:
    """Run the MQTT broker."""
    app()


def _version(v:bool) -> None:
    if v:
        typer.echo(f"{amqtt_version}")
        raise typer.Exit(code=0)


@app.command()
def broker_main(
        config_file: str | None = typer.Option(None, "-c", help="broker configuration file"),
        debug: bool = typer.Option(False, "-d", help="Enable debug messages"),
        version: bool = typer.Option(  # noqa : ARG001
            False,
            "--version",
            callback=_version,
            is_eager=True,
            help="Show version and exit",
        ),
) -> None:
    """Command-line script for running a MQTT 3.1.1 broker."""
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        broker = Broker(config, loop=loop)
    except (BrokerError, ParserError, PluginError) as exc:
        typer.echo(f"❌ Broker failed to start: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _ = loop.create_task(broker.start())  #noqa : RUF006
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(broker.shutdown())
    except Exception as exc:
        typer.echo("❌ Broker execution halted", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        loop.close()


if __name__ == "__main__":
    main()
