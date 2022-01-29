# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

from __future__ import annotations

import logging
import random

import yaml
import typing

if typing.TYPE_CHECKING:
    from amqtt.session import Session

logger = logging.getLogger(__name__)


def format_client_message(
    session: Session = None, address: str = None, port: int = None
) -> str:
    if session:
        return "(client id=%s)" % session.client_id
    elif address is not None and port is not None:
        return "(client @=%s:%d)" % (address, port)
    else:
        return "(unknown client)"


def gen_client_id() -> str:
    """Generates random client ID"""
    gen_id = "amqtt/"

    for i in range(7, 23):
        gen_id += chr(random.randint(0, 74) + 48)
    return gen_id


def read_yaml_config(config_file: str) -> dict:
    config = None
    try:
        with open(config_file) as stream:
            config = yaml.full_load(stream)
    except yaml.YAMLError as exc:
        logger.error("Invalid config_file %s: %r", config_file, exc)
    return config
