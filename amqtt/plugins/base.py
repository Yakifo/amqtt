from dataclasses import dataclass, is_dataclass
from typing import Any, Generic, TypeVar, cast

from amqtt.contexts import Action, BaseContext
from amqtt.session import Session

C = TypeVar("C", bound=BaseContext)


class BasePlugin(Generic[C]):
    """The base from which all plugins should inherit.

    Type Parameters
    ---------------
    C:
        A BaseContext: either BrokerContext or ClientContext, depending on plugin usage

    Attributes
    ----------
    context (C):
        Information about the environment in which this plugin is executed. Modifying
        the broker or client state should happen through methods available here.

    config (self.Config):
        An instance of the Config dataclass defined by the plugin (or an empty dataclass, if not
        defined). If using entrypoint- or mixed-style configuration, use `_get_config_option()`
        to access the variable.

    """

    def __init__(self, context: C) -> None:
        self.context: C = context
        # since the PluginManager will hydrate the config from a plugin's `Config` class, this is a safe cast
        self.config = cast("self.Config", context.config)  # type: ignore[name-defined]

    # Deprecated: included to support entrypoint-style configs. Replaced by dataclass Config class.
    def _get_config_section(self, name: str) -> dict[str, Any] | None:

        if not self.context.config or not hasattr(self.context.config, "get") or not self.context.config.get(name, None):
            return None

        section_config: int | dict[str, Any] | None = self.context.config.get(name, None)
        # mypy has difficulty excluding int from `config`'s type, unless there's an explicit check
        if isinstance(section_config, int):
            return None
        return section_config

    # Deprecated : supports entrypoint-style configs as well as dataclass configuration.
    def _get_config_option(self, option_name: str, default: Any=None) -> Any:
        if not self.context.config:
            return default

        if is_dataclass(self.context.config):
            # overloaded context.config for BasePlugin `Config` class, so ignoring static type check
            return getattr(self.context.config, option_name.replace("-", "_"), default) # type: ignore[unreachable]
        if option_name in self.context.config:
            return self.context.config[option_name]
        return default

    @dataclass
    class Config:
        """Override to define the configuration and defaults for plugin."""

    async def close(self) -> None:
        """Override if plugin needs to clean up resources upon shutdown."""


class BaseTopicPlugin(BasePlugin[BaseContext]):
    """Base class for topic plugins."""

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        self.topic_config: dict[str, Any] | None = self._get_config_section("topic-check")
        if not bool(self.topic_config) and not is_dataclass(self.context.config):
            self.context.logger.warning("'topic-check' section not found in context configuration")

    def _get_config_option(self, option_name: str, default: Any=None) -> Any:
        if not self.context.config:
            return default

        if is_dataclass(self.context.config):
            # overloaded context.config for BasePlugin `Config` class, so ignoring static type check
            return getattr(self.context.config, option_name.replace("-", "_"), default) # type: ignore[unreachable]
        if self.topic_config and option_name in self.topic_config:
            return self.topic_config[option_name]
        return default

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
        return bool(self.topic_config) or is_dataclass(self.context.config)


class BaseAuthPlugin(BasePlugin[BaseContext]):
    """Base class for authentication plugins."""

    def _get_config_option(self, option_name: str, default: Any=None) -> Any:
        if not self.context.config:
            return default

        if is_dataclass(self.context.config):
            # overloaded context.config for BasePlugin `Config` class, so ignoring static type check
            return getattr(self.context.config, option_name.replace("-", "_"), default)  # type: ignore[unreachable]
        if self.auth_config and option_name in self.auth_config:
            return self.auth_config[option_name]
        return default

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        self.auth_config: dict[str, Any] | None = self._get_config_section("auth")
        if not bool(self.auth_config) and not is_dataclass(self.context.config):
            # auth config section not found and Config dataclass not provided
            self.context.logger.warning("'auth' section not found in context configuration")


    async def authenticate(self, *, session: Session) -> bool | None:
        """Logic for session authentication.

        Args:
            session: amqtt.session.Session

        Returns:
            - `True` if user is authentication succeed, `False` if user authentication fails
            - `None` if authentication can't be achieved (then plugin result is then ignored)

        """
        return bool(self.auth_config) or is_dataclass(self.context.config)
