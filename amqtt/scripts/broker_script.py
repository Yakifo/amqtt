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

from docopt import docopt

import amqtt
from amqtt.broker import Broker
from amqtt.utils import read_yaml_config

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the MQTT broker."""
    arguments = docopt(__doc__, version=amqtt.__version__)
    formatter = "[%(asctime)s] :: %(levelname)s - %(message)s"

    level = logging.DEBUG if arguments["-d"] else logging.INFO
    logging.basicConfig(level=level, format=formatter)

    config = None
    if arguments["-c"]:
        config = read_yaml_config(arguments["-c"])
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
