"""amqtt_sub - MQTT 3.1.1 publisher.

Usage:
    amqtt_sub --version
    amqtt_sub (-h | --help)
    amqtt_sub --url BROKER_URL -t TOPIC... [-n COUNT] [-c CONFIG_FILE] [-i CLIENT_ID] [-q | --qos QOS] [-d] [-k KEEP_ALIVE] [--clean-session] [--ca-file CAFILE] [--ca-path CAPATH] [--ca-data CADATA] [ --will-topic WILL_TOPIC [--will-message WILL_MESSAGE] [--will-qos WILL_QOS] [--will-retain] ] [--extra-headers HEADER]

Options:
    -h --help           Show this screen.
    --version           Show version.
    --url BROKER_URL    Broker connection URL (must conform to MQTT URI scheme)
    -c CONFIG_FILE      Broker configuration file (YAML format)
    -i CLIENT_ID        Id to use as client ID.
    -n COUNT            Number of messages to read before ending.
    -q | --qos QOS      Quality of service desired to receive messages, from 0, 1 and 2. Defaults to 0.
    -t TOPIC...         Topic filter to subscribe
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
import contextlib
import json
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Any

from docopt import docopt

import amqtt
from amqtt.client import MQTTClient
from amqtt.errors import ConnectError, MQTTError
from amqtt.mqtt.constants import QOS_0
from amqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


def _gen_client_id() -> str:
    pid = os.getpid()
    hostname = socket.gethostname()
    return f"amqtt_sub/{pid}-{hostname}"


def _get_qos(arguments: dict[str, Any]) -> int:
    try:
        return int(arguments["--qos"][0])
    except (ValueError, IndexError):
        return QOS_0


def _get_extra_headers(arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        extra_headers: dict[str, Any] = json.loads(arguments["--extra-headers"])
        return extra_headers
    except (json.JSONDecodeError, TypeError):
        return {}


async def do_sub(client: MQTTClient, arguments: dict[str, Any]) -> None:
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
        filters = [(topic, qos) for topic in arguments["-t"]]
        await client.subscribe(filters)

        max_count = int(arguments["-n"]) if arguments["-n"] else None
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
        loop.run_until_complete(do_sub(client, arguments))
    loop.close()


if __name__ == "__main__":
    main()
