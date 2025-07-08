__all__ = ["PluginManager", "get_plugin_manager"]

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
import contextlib
import copy
from importlib.metadata import EntryPoint, EntryPoints, entry_points
from inspect import iscoroutinefunction
import logging
from typing import Any, Generic, NamedTuple, Optional, TypeAlias, TypeVar, cast
import warnings

from dacite import Config as DaciteConfig, DaciteError, from_dict

from amqtt.contexts import Action, BaseContext
from amqtt.errors import PluginCoroError, PluginImportError, PluginInitError, PluginLoadError
from amqtt.events import BrokerEvents, Events, MQTTEvents
from amqtt.plugins.base import BaseAuthPlugin, BasePlugin, BaseTopicPlugin
from amqtt.session import Session
from amqtt.utils import import_string


class Plugin(NamedTuple):
    name: str
    ep: EntryPoint
    object: Any


plugins_manager: dict[str, "PluginManager[Any]"] = {}


def get_plugin_manager(namespace: str) -> "PluginManager[Any] | None":
    """Get the plugin manager for a given namespace.

    :param namespace: The namespace of the plugin manager to retrieve.
    :return: The plugin manager for the given namespace, or None if it doesn't exist.
    """
    return plugins_manager.get(namespace)


def safe_issubclass(sub_class: Any, super_class: Any) -> bool:
    try:
        return issubclass(sub_class, super_class)
    except TypeError:
        return False


AsyncFunc: TypeAlias = Callable[..., Coroutine[Any, Any, None]]
C = TypeVar("C", bound=BaseContext)

class PluginManager(Generic[C]):
    """Wraps contextlib Entry point mechanism to provide a basic plugin system.

    Plugins are loaded for a given namespace (group). This plugin manager uses coroutines to
    run plugin calls asynchronously in an event queue.
    """

    def __init__(self, namespace: str, context: C | None, loop: asyncio.AbstractEventLoop | None = None) -> None:
        try:
            self._loop = loop if loop is not None else asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self.logger = logging.getLogger(namespace)
        self.context = context if context is not None else BaseContext()
        self.context.loop = self._loop
        self._plugins: list[BasePlugin[C]] = []
        self._auth_plugins: list[BaseAuthPlugin] = []
        self._topic_plugins: list[BaseTopicPlugin] = []
        self._event_plugin_callbacks: dict[str, list[AsyncFunc]] = defaultdict(list)
        self._is_topic_filtering_enabled = False
        self._is_auth_filtering_enabled = False

        self._load_plugins(namespace)
        self._fired_events: list[asyncio.Future[Any]] = []
        plugins_manager[namespace] = self

    @property
    def app_context(self) -> BaseContext:
        return self.context

    def _load_plugins(self, namespace: str | None = None) -> None:
        """Load plugins from entrypoint or config dictionary.

        config style is now recommended; entrypoint has been deprecated
        Example:
            config = {
                'listeners':...,
                'plugins': {
                    'myproject.myfile.MyPlugin': {}
            }
        """
        if self.app_context.config and self.app_context.config.get("plugins", None) is not None:
            # plugins loaded directly from config dictionary


            if "auth" in self.app_context.config:
                self.logger.warning("Loading plugins from config will ignore 'auth' section of config")
            if "topic-check" in self.app_context.config:
                self.logger.warning("Loading plugins from config will ignore 'topic-check' section of config")

            plugins_config: list[Any] | dict[str, Any] = self.app_context.config.get("plugins", [])

            # if the config was generated from yaml, the plugins maybe a list instead of a dictionary; transform before loading
            #
            # plugins:
            #   - myproject.myfile.MyPlugin:

            if isinstance(plugins_config, list):
                plugins_info: dict[str, Any] = {}
                for plugin_config in plugins_config:
                    if isinstance(plugin_config, str):
                        plugins_info.update({plugin_config: {}})
                    elif not isinstance(plugin_config, dict):
                        msg = "malformed 'plugins' configuration"
                        raise PluginLoadError(msg)
                    else:
                        plugins_info.update(plugin_config)
                self._load_str_plugins(plugins_info)
            elif isinstance(plugins_config, dict):
                self._load_str_plugins(plugins_config)
        else:
            if not namespace:
                msg = "Namespace needs to be provided for EntryPoint plugin definitions"
                raise PluginLoadError(msg)

            warnings.warn(
                "Loading plugins from EntryPoints is deprecated and will be removed in a future version."
                " Use `plugins` section of config instead.",
                DeprecationWarning,
                stacklevel=2
            )

            self._load_ep_plugins(namespace)

        # for all the loaded plugins, find all event callbacks
        for plugin in self._plugins:
            for event in list(BrokerEvents) + list(MQTTEvents):
                if awaitable := getattr(plugin, f"on_{event}", None):
                    if not iscoroutinefunction(awaitable):
                        msg = f"'on_{event}' for '{plugin.__class__.__name__}' is not a coroutine'"
                        raise PluginImportError(msg)
                    self.logger.debug(f"'{event}' handler found for '{plugin.__class__.__name__}'")
                    self._event_plugin_callbacks[event].append(awaitable)

    def _load_ep_plugins(self, namespace:str) -> None:
        """Load plugins from `pyproject.toml` entrypoints. Deprecated."""
        self.logger.debug(f"Loading plugins for namespace {namespace}")
        auth_filter_list = []
        topic_filter_list = []
        if self.app_context.config and "auth" in self.app_context.config:
            auth_filter_list = self.app_context.config["auth"].get("plugins", None)
        if self.app_context.config and "topic-check" in self.app_context.config:
            topic_filter_list = self.app_context.config["topic-check"].get("plugins", None)

        ep: EntryPoints | list[EntryPoint] = []
        if hasattr(entry_points(), "select"):
            ep = entry_points().select(group=namespace)
        elif namespace in entry_points():
            ep = [entry_points()[namespace]]

        for item in ep:
            ep_plugin = self._load_ep_plugin(item)
            if ep_plugin is not None:
                self._plugins.append(ep_plugin.object)
                # maintain legacy behavior that if there is no list, use all auth plugins
                if ((auth_filter_list is None or ep_plugin.name in auth_filter_list)
                        and hasattr(ep_plugin.object, "authenticate")):
                    self._auth_plugins.append(ep_plugin.object)
                # maintain legacy behavior that if there is no list, use all topic plugins
                if ((topic_filter_list is None or ep_plugin.name in topic_filter_list)
                        and hasattr(ep_plugin.object, "topic_filtering")):
                    self._topic_plugins.append(ep_plugin.object)
                self.logger.debug(f" Plugin {item.name} ready")

    def _load_ep_plugin(self, ep: EntryPoint) -> Plugin | None:
        """Load plugins from `pyproject.toml` entrypoints. Deprecated."""
        try:
            self.logger.debug(f" Loading plugin {ep!s}")
            plugin = ep.load()

        except ImportError as e:
            self.logger.debug(f"Plugin import failed: {ep!r}", exc_info=True)
            raise PluginImportError(ep) from e

        self.logger.debug(f" Initializing plugin {ep!s}")

        plugin_context = copy.copy(self.app_context)
        plugin_context.logger = self.logger.getChild(ep.name)
        try:
            obj = plugin(plugin_context)
            return Plugin(ep.name, ep, obj)
        except Exception as e:
            self.logger.debug(f"Plugin init failed: {ep!r}", exc_info=True)
            raise PluginInitError(ep) from e

    def _load_str_plugins(self, plugins_info: dict[str, Any]) -> None:

        self.logger.info("Loading plugins from config")
        # legacy had a filtering 'enabled' flag, even if plugins were loaded/listed
        self._is_topic_filtering_enabled = True
        self._is_auth_filtering_enabled = True
        for plugin_path, plugin_config in plugins_info.items():

            plugin = self._load_str_plugin(plugin_path, plugin_config)
            self._plugins.append(plugin)

            # make sure that authenticate and topic filtering plugins have the appropriate async signature
            if isinstance(plugin, BaseAuthPlugin):
                if not iscoroutinefunction(plugin.authenticate):
                    msg = f"Auth plugin {plugin_path} has non-async authenticate method."
                    raise PluginCoroError(msg)
                self._auth_plugins.append(plugin)
            if isinstance(plugin, BaseTopicPlugin):
                if not iscoroutinefunction(plugin.topic_filtering):
                    msg = f"Topic plugin {plugin_path} has non-async topic_filtering method."
                    raise PluginCoroError(msg)
                self._topic_plugins.append(plugin)

    def _load_str_plugin(self, plugin_path: str, plugin_cfg: dict[str, Any] | None = None) -> "BasePlugin[C]":
        """Load plugin from string dotted path: mymodule.myfile.MyPlugin."""
        try:
            plugin_class: Any =  import_string(plugin_path)
        except ImportError as ep:
            msg = f"Plugin import failed: {plugin_path}"
            raise PluginImportError(msg) from ep

        if not safe_issubclass(plugin_class, BasePlugin):
            msg = f"Plugin {plugin_path} is not a subclass of 'BasePlugin'"
            raise PluginLoadError(msg)

        plugin_context = copy.copy(self.app_context)
        plugin_context.logger = self.logger.getChild(plugin_class.__name__)
        try:
            # populate the config based on the inner dataclass called `Config`
            #   use `dacite` package to type check
            plugin_context.config = from_dict(data_class=plugin_class.Config,
                                              data=plugin_cfg or {},
                                              config=DaciteConfig(strict=True))
        except DaciteError as e:
            raise PluginLoadError from e
        except TypeError as e:
            msg = f"Could not marshall 'Config' of {plugin_path}; should be a dataclass."
            raise PluginLoadError(msg) from e

        try:
            pc = plugin_class(plugin_context)
            self.logger.debug(f"Loading plugin {plugin_path}")
            return cast("BasePlugin[C]", pc)
        except Exception as e:
            self.logger.debug(f"Plugin init failed: {plugin_class.__name__}", exc_info=True)
            raise PluginInitError(plugin_class) from e

    def get_plugin(self, name: str) -> Optional["BasePlugin[C]"]:
        """Get a plugin by its name from the plugins loaded for the current namespace.

        Only used for testing purposes to verify plugin loading correctly.

        :param name:
        :return:
        """
        for p in self._plugins:
            if p.__class__.__name__ == name:
                return p
        return None

    def is_topic_filtering_enabled(self) -> bool:
        topic_config = self.app_context.config.get("topic-check", {}) if self.app_context.config else {}
        if isinstance(topic_config, dict):
            return topic_config.get("enabled", False) or self._is_topic_filtering_enabled
        return False or self._is_topic_filtering_enabled

    async def close(self) -> None:
        """Free PluginManager resources and cancel pending event methods."""
        await self.map_plugin_close()
        for task in self._fired_events:
            task.cancel()
        self._fired_events.clear()

    @property
    def plugins(self) -> list["BasePlugin[C]"]:
        """Get the loaded plugins list.

        :return:
        """
        return self._plugins

    def _schedule_coro(self, coro: Awaitable[str | bool | None]) -> asyncio.Future[str | bool | None]:
        return asyncio.ensure_future(coro)

    def _clean_fired_events(self, future: asyncio.Future[Any]) -> None:
        with contextlib.suppress(KeyError, ValueError):
            self._fired_events.remove(future)

    async def fire_event(self, event_name: Events, *, wait: bool = False, **method_kwargs: Any) -> None:
        """Fire an event to plugins.

        PluginManager schedules async calls for each plugin on method called "on_" + event_name.
        For example, on_connect will be called on event 'connect'.
        Method calls are scheduled in the async loop. wait parameter must be set to true
        to wait until all methods are completed.
        :param event_name:
        :param method_kwargs:
        :param wait: indicates if fire_event should wait for plugin calls completion (True), or not
        :return:
        """
        tasks: list[asyncio.Future[Any]] = []

        # check if any plugin has defined a callback for this event, skip if none
        if event_name not in self._event_plugin_callbacks:
            return

        for event_awaitable in self._event_plugin_callbacks[event_name]:

            async def call_method(method: AsyncFunc, kwargs: dict[str, Any]) -> Any:
                return await method(**kwargs)

            coro_instance: Awaitable[Any] = call_method(event_awaitable, method_kwargs)
            tasks.append(asyncio.ensure_future(coro_instance))
            tasks[-1].add_done_callback(self._clean_fired_events)

        self._fired_events.extend(tasks)
        if wait and tasks:
            await asyncio.wait(tasks)
        self.logger.debug(f"Plugins len(_fired_events)={len(self._fired_events)}")

    @staticmethod
    async def _map_plugin_method(
        plugins: list["BasePlugin[C]"],
        method_name: str,
        method_kwargs: dict[str, Any],
    ) -> dict["BasePlugin[C]", str | bool | None]:
        """Call plugin coroutines.

        :param plugins: List of plugins to execute the method on
        :param method_name: Name of the method to call on each plugin
        :param method_kwargs: Keyword arguments to pass to the method
        :return: dict containing return from coro call for each plugin.
        """
        tasks: list[asyncio.Future[Any]] = []

        for plugin in plugins:
            if not hasattr(plugin, method_name):
                continue

            async def call_method(p: "BasePlugin[C]", kwargs: dict[str, Any]) -> Any:
                method = getattr(p, method_name)
                return await method(**kwargs)

            coro_instance: Awaitable[Any] = call_method(plugin, method_kwargs)
            tasks.append(asyncio.ensure_future(coro_instance))

        ret_dict: dict[BasePlugin[C], str | bool | None] = {}
        if tasks:
            ret_list = await asyncio.gather(*tasks)
            ret_dict = dict(zip(plugins, ret_list, strict=False))

        return ret_dict

    async def map_plugin_auth(self, *, session: Session) -> dict["BasePlugin[C]", str | bool | None]:
        """Schedule a coroutine for plugin 'authenticate' calls.

        :param session: the client session associated with the authentication check
        :return: dict containing return from coro call for each plugin.
        """
        return await self._map_plugin_method(
            self._auth_plugins, "authenticate", {"session": session })  # type: ignore[arg-type]

    async def map_plugin_topic(
        self, *, session: Session, topic: str, action: "Action"
    ) -> dict["BasePlugin[C]", str | bool | None]:
        """Schedule a coroutine for plugin 'topic_filtering' calls.

        :param session: the client session associated with the topic_filtering check
        :param topic: the topic that needs to be filtered
        :param action: the action being executed
        :return: dict containing return from coro call for each plugin.
        """
        return await self._map_plugin_method(
            self._topic_plugins, "topic_filtering",   # type: ignore[arg-type]
            {"session": session, "topic": topic, "action": action}
        )

    async def map_plugin_close(self) -> None:
        """Schedule a coroutine for plugin 'close' calls.

        :return: dict containing return from coro call for each plugin.
        """
        await self._map_plugin_method(self._plugins, "close", {})
