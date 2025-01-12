"""amqtt_pub - MQTT 3.1.1 publisher.

Usage:
    amqtt_pub --version
    amqtt_pub (-h | --help)
    amqtt_pub --url BROKER_URL -t TOPIC (-f FILE | -l | -m MESSAGE | -n | -s) [-c CONFIG_FILE] [-i CLIENT_ID] [-q | --qos QOS] [-d] [-k KEEP_ALIVE] [--clean-session] [--ca-file CAFILE] [--ca-path CAPATH] [--ca-data CADATA] [ --will-topic WILL_TOPIC [--will-message WILL_MESSAGE] [--will-qos WILL_QOS] [--will-retain] ] [--extra-headers HEADER] [-r]

Options:
    -h --help           Show this screen.
    --version           Show version.
    --url BROKER_URL    Broker connection URL (must conform to MQTT URI scheme (see https://github.com/mqtt/mqtt.github.io/wiki/URI-Scheme>)
    -c CONFIG_FILE      Broker configuration file (YAML format)
    -i CLIENT_ID        Id to use as client ID.
    -q | --qos QOS      Quality of service to use for the message, from 0, 1, and 2. Defaults to 0.
    -r                  Set retain flag on connect
    -t TOPIC            Message topic
    -m MESSAGE          Message data to send
    -f FILE             Read file by line and publish message for each line
    -s                  Read from stdin and publish message for each line
    -k KEEP_ALIVE       Keep alive timeout in seconds
    --clean-session     Clean session on connect (defaults to False)
    --ca-file CAFILE    CA file
    --ca-path CAPATH    CA Path
    --ca-data CADATA    CA data
    --will-topic WILL_TOPIC
    --will-message WILL_MESSAGE
    --will-qos WILL_QOS
    --will-retain
    --extra-headers EXTRA_HEADERS      JSON object with key-value pairs of additional headers for websocket connections
    -d                  Enable debug messages
"""  # noqa: E501

import asyncio
from collections.abc import Generator
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from docopt import docopt

import amqtt
from amqtt.client import MQTTClient
from amqtt.errors import ConnectError
from amqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


def _gen_client_id() -> str:
    import os
    import socket

    pid = os.getpid()
    hostname = socket.gethostname()
    return f"amqtt_pub/{pid}-{hostname}"


def _get_qos(arguments: dict[str, Any]) -> int | None:
    try:
        return int(arguments["--qos"][0])
    except (ValueError, IndexError):
        return None


def _get_extra_headers(arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        extra_headers: dict[str, Any] = json.loads(arguments["--extra-headers"])
        return extra_headers
    except (json.JSONDecodeError, TypeError):
        return {}


def _get_message(arguments: dict[str, Any]) -> Generator[bytes | bytearray]:
    if arguments["-n"]:
        yield b""
    if arguments["-m"]:
        yield arguments["-m"].encode(encoding="utf-8")
    if arguments["-f"]:
        try:
            with Path(arguments["-f"]).open() as f:
                for line in f:
                    yield line.encode(encoding="utf-8")
        except Exception:
            logger.exception(f"Failed to read file '{arguments['-f']}'")
    if arguments["-l"]:
        import sys

        for line in sys.stdin:
            if line:
                yield line.encode(encoding="utf-8")
    if arguments["-s"]:
        import sys

        message = bytearray()
        for line in sys.stdin:
            message.extend(line.encode(encoding="utf-8"))
        yield message


async def do_pub(client: MQTTClient, arguments: dict[str, Any]) -> None:
    running_tasks = []

    try:
        logger.info(f"{client.client_id} Connecting to broker")

        await client.connect(
            uri=arguments["--url"],
            cleansession=arguments["--clean-session"],
            cafile=arguments["--ca-file"],
            capath=arguments["--ca-path"],
            cadata=arguments["--ca-data"],
            additional_headers=_get_extra_headers(arguments),
        )

        qos = _get_qos(arguments)
        topic = arguments["-t"]
        retain = arguments["-r"]
        for message in _get_message(arguments):
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
        logger.fatal(f"Connection to '{arguments['--url']}' failed: {ce!r}")
    except asyncio.CancelledError:
        logger.fatal("Publish canceled due to previous error")


def main() -> None:
    arguments = docopt(__doc__, version=amqtt.__version__)

    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"
    level = logging.DEBUG if arguments["-d"] else logging.INFO
    logging.basicConfig(level=level, format=formatter)

    config = None
    if arguments["-c"]:
        config = read_yaml_config(arguments["-c"])
    else:
        default_config_path = Path(__file__).parent / "default_client.yaml"
        logger.debug(f"Using default configuration from {default_config_path}")
        config = read_yaml_config(default_config_path)

    loop = asyncio.get_event_loop()

    client_id = arguments.get("-i", None)
    if not client_id:
        client_id = _gen_client_id()

    if not isinstance(config, dict):
        logger.debug("Failed to correctly initialize config")
        return

    if arguments["-k"]:
        config["keep_alive"] = int(arguments["-k"])

    if arguments["--will-topic"] and arguments["--will-message"] and arguments["--will-qos"]:
        config["will"] = {
            "topic": arguments["--will-topic"],
            "message": arguments["--will-message"].encode("utf-8"),
            "qos": int(arguments["--will-qos"]),
            "retain": arguments["--will-retain"],
        }

    client = MQTTClient(client_id=client_id, config=config)
    with contextlib.suppress(KeyboardInterrupt):
        loop.run_until_complete(do_pub(client, arguments))
    loop.close()


if __name__ == "__main__":
    main()
