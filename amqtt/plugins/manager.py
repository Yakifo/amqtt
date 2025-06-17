__all__ = ["BaseContext", "PluginManager", "get_plugin_manager"]

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
import contextlib
import copy
from importlib.metadata import EntryPoint, EntryPoints, entry_points
from inspect import iscoroutinefunction
import logging
from typing import TYPE_CHECKING, Any, Generic, NamedTuple, Optional, TypeAlias, TypeVar

from amqtt.errors import PluginImportError, PluginInitError
from amqtt.events import BrokerEvents, Events, MQTTEvents
from amqtt.session import Session

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from amqtt.broker import Action
    from amqtt.plugins.authentication import BaseAuthPlugin
    from amqtt.plugins.base import BasePlugin
    from amqtt.plugins.topic_checking import BaseTopicPlugin

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


class BaseContext:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.logger: logging.Logger = _LOGGER
        self.config: dict[str, Any] | None = None


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
        self._load_plugins(namespace)
        self._fired_events: list[asyncio.Future[Any]] = []
        plugins_manager[namespace] = self

    @property
    def app_context(self) -> BaseContext:
        return self.context

    def _load_plugins(self, namespace: str) -> None:

        self.logger.debug(f"Loading plugins for namespace {namespace}")

        auth_filter_list = []
        topic_filter_list = []
        if self.app_context.config and "auth" in self.app_context.config:
            auth_filter_list = self.app_context.config["auth"].get("plugins", [])
        if self.app_context.config and "topic" in self.app_context.config:
            topic_filter_list = self.app_context.config["topic"].get("plugins", [])

        ep: EntryPoints | list[EntryPoint] = []
        if hasattr(entry_points(), "select"):
            ep = entry_points().select(group=namespace)
        elif namespace in entry_points():
            ep = [entry_points()[namespace]]

        for item in ep:
            ep_plugin = self._load_ep_plugin(item)
            if ep_plugin is not None:
                self._plugins.append(ep_plugin.object)
                if ((not auth_filter_list or ep_plugin.name in auth_filter_list)
                        and hasattr(ep_plugin.object, "authenticate")):
                    self._auth_plugins.append(ep_plugin.object)
                if ((not topic_filter_list or ep_plugin.name in topic_filter_list)
                        and hasattr(ep_plugin.object, "topic_filtering")):
                    self._topic_plugins.append(ep_plugin.object)
                self.logger.debug(f" Plugin {item.name} ready")

        for plugin in self._plugins:
            for event in list(BrokerEvents) + list(MQTTEvents):
                if awaitable := getattr(plugin, f"on_{event}", None):
                    if not iscoroutinefunction(awaitable):
                        msg = f"'on_{event}' for '{plugin.__class__.__name__}' is not a coroutine'"
                        raise PluginImportError(msg)
                    self.logger.debug(f"'{event}' handler found for '{plugin.__class__.__name__}'")
                    self._event_plugin_callbacks[event].append(awaitable)

    def _load_ep_plugin(self, ep: EntryPoint) -> Plugin | None:
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

    def get_plugin(self, name: str) -> Optional["BasePlugin[C]"]:
        """Get a plugin by its name from the plugins loaded for the current namespace.

        :param name:
        :return:
        """
        for p in self._plugins:
            if p.__class__.__name__ == name:
                return p
        return None

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

            def clean_fired_events(future: asyncio.Future[Any]) -> None:
                with contextlib.suppress(KeyError, ValueError):
                    self._fired_events.remove(future)

            tasks[-1].add_done_callback(clean_fired_events)

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
