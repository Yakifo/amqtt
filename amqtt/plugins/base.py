from typing import Any

from amqtt.broker import BrokerContext


class BasePlugin:
    """The base from which all plugins should inherit."""

    def __init__(self, context: BrokerContext) -> None:
        self.context = context

    def _get_config_section(self, name: str) -> dict[str, Any] | None:
        if not self.context.config or not hasattr(self.context.config, name):
            return None
        section_config: int | dict[str, Any] | None = self.context.config.get(name, None)
        # mypy has difficulty excluding int from `config`'s type, unless isinstance` is its own check
        if isinstance(section_config, int):
            return None
        return section_config
