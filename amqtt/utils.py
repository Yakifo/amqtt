from __future__ import annotations

from importlib import import_module
import logging
from pathlib import Path
import secrets
import string
import sys
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


def cached_import(module_path: str, class_name: str | None = None) -> Any:
    """Return cached import of a class from a module path (or retrieve, cache and then return)."""
    # Check whether module is loaded and fully initialized.
    if not ((module := sys.modules.get(module_path))
            and (spec := getattr(module, "__spec__", None))
            and getattr(spec, "_initializing", False) is False):
        module = import_module(module_path)
    if class_name:
        return getattr(module, class_name)
    return module


def import_string(dotted_path: str) -> Any:
    """Import a dotted module path.

    Returns:
         attribute/class designated by the last name in the path

    Raises:
         ImportError (if the import failed)

    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        msg = f"{dotted_path} doesn't look like a module path"
        raise ImportError(msg) from err

    try:
        return cached_import(module_path, class_name)
    except AttributeError as err:
        msg = f'Module "{module_path}" does not define a "{class_name}" attribute/class'

        raise ImportError(msg) from err
