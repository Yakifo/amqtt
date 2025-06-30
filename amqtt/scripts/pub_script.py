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
    topic: str,
    message_input: MessageInput,
    ca_info: CAInfo,
    url: str | None = None,
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
        logger.fatal(f"Connection to '{client.session.broker_uri if client.session else url}' failed")
        raise ConnectError from ce
    except asyncio.CancelledError as ce:
        logger.fatal("Publish canceled due to previous error")
        raise asyncio.CancelledError from ce

app = typer.Typer(add_completion=False, rich_markup_mode=None)


def main() -> None:
    """Entry point for the amqtt publisher."""
    app()


def _version(v: bool) -> None:
    if v:
        typer.echo(f"{amqtt_version}")
        raise typer.Exit(code=0)

@app.command()
def publisher_main(  # pylint: disable=R0914,R0917  # noqa : PLR0913
    url: str | None = typer.Option(None, "--url", help="Broker connection URL, *must conform to MQTT or URI scheme: `[mqtt(s)|ws(s)]://<username:password>@HOST:port`*"),
    config_file: str | None = typer.Option(None, "-c", "--config-file", help="Client configuration file"),
    client_id: str | None = typer.Option(None, "-i", "--client-id", help="client identification for mqtt connection. *default: process id and the hostname of the client*"),
    qos: int = typer.Option(0, "--qos", "-q", help="Quality of service (0, 1, or 2)"),
    retain: bool = typer.Option(False, "-r", help="Set retain flag on connect"),
    topic: str = typer.Option(..., "-t", "--topic", help="Message topic"),
    message: str | None = typer.Option(None, "-m", "--message", help="Message data to send"),
    file: str | None = typer.Option(None, "-f", "--file", help="Path to file, will publish each line as a separate message."),
    stdin: bool = typer.Option(False, "-s", "--stdin", help="Read from standard input, all content read is sent as a single message."),
    lines: bool = typer.Option(False, "-l", "--lines", help="Read from stdin, will publish message for each line."),
    no_message: bool = typer.Option(False, "-n", "--no-message", help="Publish an empty (null, zero length) message"),
    keep_alive: int | None = typer.Option(None, "-k", help="Keep alive timeout, in seconds."),
    clean_session: bool = typer.Option(False, "--clean-session", help="Clean session on connect. *default: False*"),
    ca_file: str | None = typer.Option(None, "--ca-file", help="Define the path to a file containing PEM encoded CA certificates that are trusted. Used to enable SSL communication."),
    ca_path: str | None = typer.Option(None, "--ca-path", help="Define the path to a directory containing PEM encoded CA certificates that are trusted. Used to enable SSL communication."),
    ca_data: str | None = typer.Option(None, "--ca-data", help="Set the PEM encoded CA certificates that are trusted. Used to enable SSL communication."),
    will_topic: str | None = typer.Option(None, "--will-topic", help="The topic on which to send a Will, in the event that the client disconnects unexpectedly."),
    will_message: str | None = typer.Option(None, "--will-message", help="Specify a message that will be stored by the broker and sent out if this client disconnects unexpectedly. *required if `--will-topic` is specified*."),
    will_qos: int = typer.Option(0, "--will-qos", help="The QoS to use for the Will. *default: 0, only valid if `--will-topic` is specified*"),
    will_retain: bool = typer.Option(False, "--will-retain", help="If the client disconnects unexpectedly the message sent out will be treated as a retained message. *only valid, if `--will-topic` is specified*"),
    extra_headers_json: str | None = typer.Option(None, "--extra-headers", help="Specify a JSON object string with key-value pairs representing additional headers that are transmitted on the initial connection. *websocket connections only*."),
    debug: bool = typer.Option(False, "-d", help="Enable debug messages"),
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show version and exit"), # noqa : ARG001
) -> None:
    """Command-line MQTT client for publishing simple messages."""
    provided = [bool(message), bool(file), stdin, lines, no_message]
    if sum(provided) != 1:
        typer.echo("❌ You must provide exactly one of --message, --file, --stdin, --lines or --no-message", err=True)
        raise typer.Exit(code=1)

    if bool(will_message) != bool(will_topic):
        typer.echo("❌ must specify both 'will_message' and 'will_topic' ")
        raise typer.Exit(code=1)

    if will_retain and not (will_message and will_topic):
        typer.echo("❌ 'will-retain' only valid if 'will_message' and 'will_topic' are specified.", err=True)
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

    if not client_id:
        client_id = _gen_client_id()

    if not isinstance(config, dict):
        logger.debug("Failed to correctly initialize config")
        return

    if keep_alive:
        config["keep_alive"] = int(keep_alive)

    if will_topic and will_message:
        config["will"] = {
            "topic": will_topic,
            "message": will_message,
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
            asyncio.run(
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
        except (ClientError, ConnectError) as exc:
            typer.echo("❌ Connection failed", err=True)
            raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    typer.run(main)
