from typing import Any, Generic, TypeVar

from amqtt.broker import Action
from amqtt.plugins.manager import BaseContext
from amqtt.session import Session

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


class BaseTopicPlugin(BasePlugin[BaseContext]):
    """Base class for topic plugins."""

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        self.topic_config: dict[str, Any] | None = self._get_config_section("topic-check")
        if self.topic_config is None:
            self.context.logger.warning("'topic-check' section not found in context configuration")

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool:
        """Logic for filtering out topics.

        Args:
            session: amqtt.session.Session
            topic: str
            action: amqtt.broker.Action

        Returns:
            bool: `True` if topic is allowed, `False` otherwise

        """
        if not self.topic_config:
            # auth config section not found
            self.context.logger.warning("'topic-check' section not found in context configuration")
            return False
        return True


class BaseAuthPlugin(BasePlugin[BaseContext]):
    """Base class for authentication plugins."""

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        self.auth_config: dict[str, Any] | None = self._get_config_section("auth")
        if not self.auth_config:
            self.context.logger.warning("'auth' section not found in context configuration")

    async def authenticate(self, *, session: Session) -> bool | None:
        """Logic for session authentication.

        Args:
            session: amqtt.session.Session

        Returns:
            - `True` if user is authentication succeed, `False` if user authentication fails
            - `None` if authentication can't be achieved (then plugin result is then ignored)

        """
        if not self.auth_config:
            # auth config section not found
            self.context.logger.warning("'auth' section not found in context configuration")
            return False
        return True
