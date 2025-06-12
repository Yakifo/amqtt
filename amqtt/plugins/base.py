from dataclasses import dataclass
from typing import Any

from amqtt.plugins.manager import BaseContext


class BasePlugin:
    """The base from which all plugins should inherit."""

    def __init__(self, context: BaseContext) -> None:
        self.context = context

    def _get_config_section(self, name: str) -> dict[str, Any] | None:

        if not self.context.config or not hasattr(self.context.config, 'get') or self.context.config.get(name, None):
            return None

        section_config: int | dict[str, Any] | None = self.context.config.get(name, None)
        # mypy has difficulty excluding int from `config`'s type, unless isinstance` is its own check
        if isinstance(section_config, int):
            return None
        return section_config

    @dataclass
    class Config:
        pass
