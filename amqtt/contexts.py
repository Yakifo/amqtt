from enum import Enum
import logging
from typing import TYPE_CHECKING, Any

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    import asyncio


class BaseContext:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.logger: logging.Logger = _LOGGER
        self.config: dict[str, Any] | None = None


class Action(Enum):
    """Actions issued by the broker."""

    SUBSCRIBE = "subscribe"
    PUBLISH = "publish"
