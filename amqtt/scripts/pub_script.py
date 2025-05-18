import asyncio
from collections.abc import Generator
import contextlib
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Any

import typer

from amqtt import __version__ as amqtt_version
from amqtt.client import MQTTClient
from amqtt.errors import ClientError, ConnectError
from amqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


def _gen_client_id() -> str:
    pid = os.getpid()
    hostname = socket.gethostname()
    return f"amqtt_pub/{pid}-{hostname}"


def _get_extra_headers(extra_headers_json: str | None = None) -> dict[str, Any]:
    try:
        extra_headers: dict[str, Any] = json.loads(extra_headers_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return extra_headers


@dataclass
class MessageInput:
    message_str: str | None = None
    file: str | None = None
    stdin: bool | None = False
    lines: bool | None = False
    no_message: bool | None = False

    def get_message(self) -> Generator[bytes | bytearray]:
        if self.no_message:
            yield b""
        if self.message_str:
            yield self.message_str.encode(encoding="utf-8")
        if self.file:
            try:
                with Path(self.file).open(encoding="utf-8") as f:
                    for line in f:
                        yield line.encode(encoding="utf-8")
            except Exception:
                logger.exception(f"Failed to read file '{self.file}'")
        if self.lines:
            for line in sys.stdin:
                if line:
                    yield line.encode(encoding="utf-8")
        if self.stdin:
            messages = bytearray()
            for line in sys.stdin:
                messages.extend(line.encode(encoding="utf-8"))
            yield messages


@dataclass
class CAInfo:
    ca_file: str | None = None
    ca_path: str | None = None
    ca_data: str | None = None


async def do_pub(
    client: MQTTClient,
    url: str,
    topic: str,
    message_input: MessageInput,
    ca_info: CAInfo,
    clean_session: bool = False,
    retain: bool = False,
    extra_headers_json: str | None = None,
    qos: int | None = None,
) -> None:
    """Publish the message."""
    running_tasks = []

    try:
        logger.info(f"{client.client_id} Connecting to broker")

        await client.connect(
            uri=url,
            cleansession=clean_session,
            cafile=ca_info.ca_file,
            capath=ca_info.ca_path,
            cadata=ca_info.ca_data,
            additional_headers=_get_extra_headers(extra_headers_json),
        )

        for message in message_input.get_message():
            logger.info(f"{client.client_id} Publishing to '{topic}'")
            task = asyncio.ensure_future(client.publish(topic, message, qos, retain))
            running_tasks.append(task)

        if running_tasks:
            await asyncio.wait(running_tasks)

        await client.disconnect()
        logger.info(f"{client.client_id} Disconnected from broker")
    except KeyboardInterrupt:
        await client.disconnect()
        logger.info(f"{client.client_id} Disconnected from broker")
    except ConnectError as ce:
        logger.fatal(f"Connection to '{url}' failed: {ce!r}")
    except asyncio.CancelledError:
        logger.fatal("Publish canceled due to previous error")


def main() -> None:
    """Entry point for the amqtt publisher."""
    typer.run(publisher)


def _version() -> None:
    typer.echo(f"{amqtt_version}")
    raise typer.Exit(code=0)


def publisher(  # pylint: disable=R0914,R0917  # noqa : PLR0913
    url: str = typer.Option(
        ..., "--url", help="Broker connection URL (must conform to MQTT URI scheme: mqtt://<username:password>@HOST:port)"
    ),
    config_file: str | None = typer.Option(None, "-c", "--config-file", help="Broker configuration file (YAML format)"),
    client_id: str | None = typer.Option(None, "-i", "--client-id", help="Client ID to use for the connection"),
    qos: int = typer.Option(0, "--qos", "-q", help="Quality of service (0, 1, or 2)"),
    retain: bool = typer.Option(False, "-r", help="Set retain flag on connect"),
    topic: str = typer.Option(..., "-t", help="Message topic"),
    message: str | None = typer.Option(None, "-m", help="Message data to send"),
    file: str | None = typer.Option(None, "-f", help="Read file by line and publish each line as a message"),
    stdin: bool = typer.Option(False, "-s", help="Read from stdin and publish message for first line"),
    lines: bool = typer.Option(False, "-l", help="Read from stdin and publish message for each line"),
    no_message: bool = typer.Option(False, "-n", help="Publish an empty message"),
    keep_alive: int | None = typer.Option(None, "-k", help="Keep alive timeout in seconds"),
    clean_session: bool = typer.Option(False, "--clean-session", help="Clean session on connect (defaults to False)"),
    ca_file: str | None = typer.Option(None, "--ca-file", help="CA file"),
    ca_path: str | None = typer.Option(None, "--ca-path", help="CA path"),
    ca_data: str | None = typer.Option(None, "--ca-data", help="CA data"),
    will_topic: str | None = typer.Option(None, "--will-topic", help="Last will topic"),
    will_message: str | None = typer.Option(None, "--will-message", help="Last will message"),
    will_qos: int | None = typer.Option(None, "--will-qos", help="Last will QoS"),
    will_retain: bool = typer.Option(False, "--will-retain", help="Set retain flag for last will message"),
    extra_headers_json: str | None = typer.Option(
        None, "--extra-headers", help="JSON object with key-value headers for websocket connections"
    ),
    debug: bool = typer.Option(False, "-d", help="Enable debug messages"),
    version: bool | None = typer.Option(  # noqa : ARG001
        None,
        "--version",
        callback=_version,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Run the MQTT publisher."""
    provided = [bool(message), bool(file), stdin, lines, no_message]
    if sum(provided) != 1:
        typer.echo("❌ You must provide exactly one of --config, --file, or --stdin.", err=True)
        raise typer.Exit(code=1)

    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format=formatter)

    if config_file:
        config = read_yaml_config(config_file)
    else:
        default_config_path = Path(__file__).parent / "default_client.yaml"
        logger.debug(f"Using default configuration from {default_config_path}")
        config = read_yaml_config(default_config_path)

    loop = asyncio.get_event_loop()

    if not client_id:
        client_id = _gen_client_id()

    if not isinstance(config, dict):
        logger.debug("Failed to correctly initialize config")
        return

    if keep_alive:
        config["keep_alive"] = int(keep_alive)

    if will_topic and will_message and will_qos:
        config["will"] = {
            "topic": will_topic,
            "message": will_message.encode("utf-8"),
            "qos": int(will_qos),
            "retain": will_retain,
        }

    client = MQTTClient(client_id=client_id, config=config)
    message_input = MessageInput(
        message_str=message,
        file=file,
        stdin=stdin,
        no_message=no_message,
        lines=lines,
    )
    ca_info = CAInfo(
        ca_file=ca_file,
        ca_path=ca_path,
        ca_data=ca_data,
    )
    with contextlib.suppress(KeyboardInterrupt):
        try:
            loop.run_until_complete(
                do_pub(
                    client=client,
                    message_input=message_input,
                    url=url,
                    topic=topic,
                    retain=retain,
                    clean_session=clean_session,
                    ca_info=ca_info,
                    extra_headers_json=extra_headers_json,
                    qos=qos,
                )
            )
        except (ClientError, ConnectError) as ce:
            typer.echo(f"❌ Connection failed: {ce}", err=True)
    loop.close()


if __name__ == "__main__":
    typer.run(main)
