from __future__ import annotations

import logging
from pathlib import Path
import secrets
import string
import typing
from typing import Any

import yaml

if typing.TYPE_CHECKING:
    from amqtt.session import Session

logger = logging.getLogger(__name__)


def format_client_message(
    session: Session | None = None,
    address: str | None = None,
    port: int | None = None,
) -> str:
    """Format a client message for logging."""
    if session:
        return f"(client id={session.client_id})"
    if address is not None and port is not None:
        return f"(client @={address}:{port})"
    return "(unknown client)"


def gen_client_id() -> str:
    """Generate a random client ID."""
    gen_id = "amqtt/"

    # Use secrets to generate a secure random client ID
    # Defining a valid set of characters for client ID generation
    valid_chars = string.ascii_letters + string.digits
    gen_id += "".join(secrets.choice(valid_chars) for _ in range(16))
    return gen_id


def read_yaml_config(config_file: str | Path) -> dict[str, Any] | None:
    """Read a YAML configuration file."""
    try:
        with Path(str(config_file)).open(encoding="utf-8") as stream:
            yaml_result: dict[str, Any] = yaml.full_load(stream)
            return yaml_result
    except yaml.YAMLError:
        logger.exception(f"Invalid config_file {config_file}")
        return None
