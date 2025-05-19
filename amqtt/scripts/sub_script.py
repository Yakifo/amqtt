import asyncio
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
from amqtt.errors import ConnectError, MQTTError
from amqtt.mqtt.constants import QOS_0
from amqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


def _gen_client_id() -> str:
    pid = os.getpid()
    hostname = socket.gethostname()
    return f"amqtt_sub/{pid}-{hostname}"


def _get_extra_headers(extra_headers_json: str | None = None) -> dict[str, Any]:
    try:
        extra_headers: dict[str, Any] = json.loads(extra_headers_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return extra_headers


@dataclass
class CAInfo:
    ca_file: str | None = None
    ca_path: str | None = None
    ca_data: str | None = None


async def do_sub(client: MQTTClient,
                 url: str,
                 topics: list[str],
                 ca_info: CAInfo,
                 max_count: int | None = None,
                 clean_session: bool = False,
                 extra_headers_json: str | None = None,
                 qos: int | None = None,
                 ) -> None:
    """Perform the subscription."""
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

        filters = [(topic, qos) for topic in topics]
        await client.subscribe(filters)

        count = 0
        while True:
            if max_count and count >= max_count:
                break
            try:
                message = await client.deliver_message()
                if message and message.publish_packet and message.publish_packet.data:
                    count += 1
                    sys.stdout.buffer.write(message.publish_packet.data)
                    sys.stdout.write("\n")
            except MQTTError:
                logger.debug("Error reading packet")

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
    """Entry point for the amqtt subscriber."""
    typer.run(subscribe_main)


def _version(v:bool) -> None:
    if v:
        typer.echo(f"{amqtt_version}")
        raise typer.Exit(code=0)


def subscribe_main(  # pylint: disable=R0914,R0917  # noqa : PLR0913
    url: str = typer.Option(..., help="Broker connection URL (must conform to MQTT URI scheme)", show_default=False),
    config_file: str | None = typer.Option(None, "-c", help="Broker configuration file (YAML format)"),
    client_id: str | None = typer.Option(None, "-i", help="Id to use as client ID"),
    max_count: int | None = typer.Option(None, "-n", help="Number of messages to read before ending"),
    qos: int = typer.Option(0, "--qos", "-q", help="Quality of service (0, 1, or 2)"),
    topics: list[str] = typer.Option(..., "-t", help="Topic filter to subscribe"),  # noqa: B008
    keep_alive: int | None = typer.Option(None, "-k", help="Keep alive timeout in seconds"),
    clean_session: bool = typer.Option(False, help="Clean session on connect (defaults to False)"),
    ca_file: str | None = typer.Option(None, "--ca-file", help="CA file"),
    ca_path: str | None = typer.Option(None, "--ca-path", help="CA path"),
    ca_data: str | None = typer.Option(None, "--ca-data", help="CA data"),
    will_topic: str | None = typer.Option(None, "--will-topic"),
    will_message: str | None = typer.Option(None, "--will-message"),
    will_qos: int | None = typer.Option(None, "--will-qos"),
    will_retain: bool = typer.Option(False, "--will-retain", help="Will retain flag"),
    extra_headers_json: str | None = typer.Option(None, "--extra-headers", help="JSON string of extra websocket headers"),
    debug: bool = typer.Option(False, "-d", help="Enable debug messages"),
    version: bool = typer.Option(  # noqa : ARG001
        False,
        "--version",
        callback=_version,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Run the MQTT subscriber."""
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
        config["keep_alive"] = keep_alive

    if will_topic and will_message and will_qos:
        config["will"] = {
            "topic": will_topic,
            "message": will_message.encode("utf-8"),
            "qos": int(will_qos),
            "retain": will_retain,
        }

    client = MQTTClient(client_id=client_id, config=config)
    ca_info = CAInfo(
        ca_file=ca_file,
        ca_path=ca_path,
        ca_data=ca_data,
    )
    with contextlib.suppress(KeyboardInterrupt):
        loop.run_until_complete(do_sub(client,
                                       url=url,
                                       topics=topics,
                                       ca_info=ca_info,
                                       extra_headers_json=extra_headers_json,
                                       qos=qos or QOS_0,
                                       max_count=max_count,
                                       clean_session=clean_session,
                                       ))
    loop.close()


if __name__ == "__main__":
    main()
