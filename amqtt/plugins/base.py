from typing import Any, Generic, TypeVar

from amqtt.plugins.manager import BaseContext

C = TypeVar("C", bound=BaseContext)


class BasePlugin(Generic[C]):
    """The base from which all plugins should inherit."""

    def __init__(self, context: C) -> None:
        self.context: C = context

    def _get_config_section(self, name: str) -> dict[str, Any] | None:

        if not self.context.config or not hasattr(self.context.config, "get") or not self.context.config.get(name, None):
            return None

        section_config: int | dict[str, Any] | None = self.context.config.get(name, None)
        # mypy has difficulty excluding int from `config`'s type, unless isinstance` is its own check
        if isinstance(section_config, int):
            return None
        return section_config

    async def close(self) -> None:
        """Override if plugin needs to clean up resources upon shutdown."""
