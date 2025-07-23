import logging
from typing import TYPE_CHECKING, Any

try:
    from enum import StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    import asyncio


class BaseContext:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.logger: logging.Logger = _LOGGER
        self.config: dict[str, Any] | None = None


class Action(StrEnum):
    """Actions issued by the broker."""

    SUBSCRIBE = "subscribe"
    PUBLISH = "publish"
