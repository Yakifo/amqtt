# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
"""
hbmqtt_sub - MQTT 3.1.1 publisher

Usage:
    hbmqtt_sub --version
    hbmqtt_sub (-h | --help)
    hbmqtt_sub --url BROKER_URL -t TOPIC... [-n COUNT] [-c CONFIG_FILE] [-i CLIENT_ID] [-q | --qos QOS] [-d] [-k KEEP_ALIVE] [--clean-session] [--ca-file CAFILE] [--ca-path CAPATH] [--ca-data CADATA] [ --will-topic WILL_TOPIC [--will-message WILL_MESSAGE] [--will-qos WILL_QOS] [--will-retain] ] [--extra-headers HEADER]

Options:
    -h --help           Show this screen.
    --version           Show version.
    --url BROKER_URL    Broker connection URL (musr conform to MQTT URI scheme (see https://github.com/mqtt/mqtt.github.io/wiki/URI-Scheme>)
    -c CONFIG_FILE      Broker configuration file (YAML format)
    -i CLIENT_ID        Id to use as client ID.
    -n COUNT            Number of messages to read before ending.
    -q | --qos QOS      Quality of service desired to receive messages, from 0, 1 and 2. Defaults to 0.
    -t TOPIC...         Topic filter to subcribe
    -k KEEP_ALIVE       Keep alive timeout in second
    --clean-session     Clean session on connect (defaults to False)
    --ca-file CAFILE]   CA file
    --ca-path CAPATH]   CA Path
    --ca-data CADATA    CA data
    --will-topic WILL_TOPIC
    --will-message WILL_MESSAGE
    --will-qos WILL_QOS
    --will-retain
    --extra-headers EXTRA_HEADERS      JSON object with key-value pairs of additional headers for websocket connections
    -d                  Enable debug messages
"""

import sys
import logging
import asyncio
import os
import json

import hbmqtt
from hbmqtt.client import MQTTClient, ConnectException
from hbmqtt.errors import MQTTException
from docopt import docopt
from hbmqtt.mqtt.constants import QOS_0
from hbmqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


def _gen_client_id():
    import os
    import socket

    pid = os.getpid()
    hostname = socket.gethostname()
    return "hbmqtt_sub/%d-%s" % (pid, hostname)


def _get_qos(arguments):
    try:
        return int(arguments["--qos"][0])
    except:
        return QOS_0


def _get_extra_headers(arguments):
    try:
        return json.loads(arguments["--extra-headers"])
    except:
        return {}


async def do_sub(client, arguments):

    try:
        await client.connect(
            uri=arguments["--url"],
            cleansession=arguments["--clean-session"],
            cafile=arguments["--ca-file"],
            capath=arguments["--ca-path"],
            cadata=arguments["--ca-data"],
            extra_headers=_get_extra_headers(arguments),
        )
        qos = _get_qos(arguments)
        filters = []
        for topic in arguments["-t"]:
            filters.append((topic, qos))
        await client.subscribe(filters)
        if arguments["-n"]:
            max_count = int(arguments["-n"])
        else:
            max_count = None
        count = 0
        while True:
            if max_count and count >= max_count:
                break
            try:
                message = await client.deliver_message()
                count += 1
                sys.stdout.buffer.write(message.publish_packet.data)
                sys.stdout.write("\n")
            except MQTTException:
                logger.debug("Error reading packet")
        await client.disconnect()
    except KeyboardInterrupt:
        await client.disconnect()
    except ConnectException as ce:
        logger.fatal("connection to '%s' failed: %r" % (arguments["--url"], ce))
    except asyncio.CancelledError:
        logger.fatal("Publish canceled due to previous error")


def main(*args, **kwargs):
    if sys.version_info[:2] < (3, 6):
        logger.fatal("Error: Python 3.6+ is required")
        sys.exit(-1)

    arguments = docopt(__doc__, version=hbmqtt.__version__)
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"

    if arguments["-d"]:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format=formatter)

    config = None
    if arguments["-c"]:
        config = read_yaml_config(arguments["-c"])
    else:
        config = read_yaml_config(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "default_client.yaml"
            )
        )
        logger.debug(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "default_client.yaml"
            )
        )
        logger.debug("Using default configuration")
    loop = asyncio.get_event_loop()

    client_id = arguments.get("-i", None)
    if not client_id:
        client_id = _gen_client_id()

    if arguments["-k"]:
        config["keep_alive"] = int(arguments["-k"])

    if (
        arguments["--will-topic"]
        and arguments["--will-message"]
        and arguments["--will-qos"]
    ):
        config["will"] = dict()
        config["will"]["topic"] = arguments["--will-topic"]
        config["will"]["message"] = arguments["--will-message"].encode("utf-8")
        config["will"]["qos"] = int(arguments["--will-qos"])
        config["will"]["retain"] = arguments["--will-retain"]

    client = MQTTClient(client_id=client_id, config=config, loop=loop)
    loop.run_until_complete(do_sub(client, arguments))
    loop.close()


if __name__ == "__main__":
    main()
