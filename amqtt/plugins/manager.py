__all__ = ["BaseContext", "PluginManager", "get_plugin_manager"]

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
import copy
from importlib.metadata import EntryPoint, EntryPoints, entry_points
import logging
from typing import Any, NamedTuple, TYPE_CHECKING

from amqtt.errors import MQTTError, PluginLoadError
from amqtt.session import Session
from amqtt.utils import import_string
from dacite import from_dict, Config, DaciteError

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from amqtt.plugins.base import BasePlugin
    from amqtt.plugins.authentication import BaseAuthPlugin
    from amqtt.plugins.topic_checking import BaseTopicPlugin
    from amqtt.broker import Action

class Plugin(NamedTuple):
    name: str
    ep: EntryPoint
    object: Any


plugins_manager: dict[str, "PluginManager"] = {}


def get_plugin_manager(namespace: str) -> "PluginManager | None":
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


class PluginManager:
    """Wraps contextlib Entry point mechanism to provide a basic plugin system.

    Plugins are loaded for a given namespace (group). This plugin manager uses coroutines to
    run plugin calls asynchronously in an event queue.
    """

    def __init__(self, namespace: str, context: BaseContext | None, loop: asyncio.AbstractEventLoop | None = None) -> None:
        try:
            self._loop = loop if loop is not None else asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self.logger = logging.getLogger(namespace)
        self.context = context if context is not None else BaseContext()
        self.context.loop = self._loop
        self._plugins: list[BasePlugin] = []
        self._auth_plugins: list[BaseAuthPlugin] = []
        self._topic_plugins: list[BaseTopicPlugin] = []
        self._load_plugins(namespace)
        self._fired_events: list[asyncio.Future[Any]] = []
        plugins_manager[namespace] = self

    @property
    def app_context(self) -> BaseContext:
        return self.context

    def _load_plugins(self, namespace: str) -> None:
        from amqtt.plugins.authentication import BaseAuthPlugin
        from amqtt.plugins.topic_checking import BaseTopicPlugin

        if 'plugins' in self.app_context.config:
            self.logger.info("Loading plugins from config file")
            for plugin_info in self.app_context.config['plugins']:

                if isinstance(plugin_info, dict):
                    assert len(plugin_info.keys()) == 1
                    plugin_path = list(plugin_info.keys())[0]
                    plugin_cfg = plugin_info[plugin_path]
                    plugin = self._load_str_plugin(plugin_path, plugin_cfg)
                elif isinstance(plugin_info, str):
                    plugin = self._load_str_plugin(plugin_info, {})
                else:
                    msg = 'Unexpected entry in plugins config'
                    raise PluginLoadError(msg)

                self._plugins.append(plugin)
                if isinstance(plugin, BaseAuthPlugin):
                    self._auth_plugins.append(plugin)
                if isinstance(plugin, BaseTopicPlugin):
                    self._topic_plugins.append(plugin)



        else:
            self.logger.debug(f"Loading plugins for namespace {namespace}")

            auth_filter_list = self.app_context.config['auth'].get('plugins', []) if 'auth' in self.app_context.config else []
            topic_filter_list = self.app_context.config['topic'].get('plugins', []) if 'topic' in self.app_context.config else []
            ep: EntryPoints | list[EntryPoint] = []
            if hasattr(entry_points(), "select"):
                ep = entry_points().select(group=namespace)
            elif namespace in entry_points():
                ep = [entry_points()[namespace]]

            for item in ep:
                plugin = self._load_ep_plugin(item)
                if plugin is not None:
                    self._plugins.append(plugin.object)
                    if plugin.name in auth_filter_list:
                        self._auth_plugins.append(plugin.object)
                    elif plugin.name in topic_filter_list:
                        self._topic_plugins.append(plugin.object)
                    self.logger.debug(f" Plugin {item.name} ready")

    def _load_ep_plugin(self, ep: EntryPoint) -> Plugin | None:
        try:
            self.logger.debug(f" Loading plugin {ep!s}")
            plugin = ep.load()
            self.logger.debug(f" Initializing plugin {ep!s}")

            plugin_context = copy.copy(self.app_context)
            plugin_context.logger = self.logger.getChild(ep.name)
            obj = plugin(plugin_context)
            return Plugin(ep.name, ep, obj)
        except ImportError:
            self.logger.warning(f"Plugin {ep!r} import failed")
            self.logger.debug("", exc_info=True)

        return None

    def _load_str_plugin(self, plugin_path: str, plugin_cfg: dict[str, Any] | None = None) -> 'BasePlugin':
        from amqtt.plugins.base import BasePlugin
        from amqtt.plugins.authentication import BaseAuthPlugin
        from amqtt.plugins.topic_checking import BaseTopicPlugin

        try:
            plugin_class =  import_string(plugin_path)
        except ModuleNotFoundError as ep:
            self.logger.error(f"Plugin import failed: {plugin_path}")
            raise MQTTError() from ep

        if not issubclass(plugin_class, BasePlugin):
            msg = f"Plugin {plugin_path} is not a subclass of 'BasePlugin'"
            raise PluginLoadError(msg)

        plugin_context = copy.copy(self.app_context)
        plugin_context.logger = self.logger.getChild(plugin_class.__name__)
        try:
            plugin_context.config = from_dict(data_class=plugin_class.Config, data=plugin_cfg or {}, config=Config(strict=True))
        except DaciteError as e:
            raise PluginLoadError from e

        try:
            return plugin_class(plugin_context)
        except ImportError as e:
            raise PluginLoadError from e

    # def get_plugin(self, name: str) -> Plugin | None:
    #     """Get a plugin by its name from the plugins loaded for the current namespace.
    #
    #     :param name:
    #     :return:
    #     """
    #     for p in self._plugins:
    #         if p.name == name:
    #             return p
    #     return None

    async def close(self) -> None:
        """Free PluginManager resources and cancel pending event methods."""
        await self.map_plugin_coro("close")
        for task in self._fired_events:
            task.cancel()
        self._fired_events.clear()

    @property
    def plugins(self) -> list['BasePlugin']:
        """Get the loaded plugins list.

        :return:
        """
        return self._plugins

    def _schedule_coro(self, coro: Awaitable[str | bool | None]) -> asyncio.Future[str | bool | None]:
        return asyncio.ensure_future(coro)

    async def fire_event(self, event_name: str, *args: Any, wait: bool = False, **kwargs: Any) -> None:
        """Fire an event to plugins.

        PluginManager schedules async calls for each plugin on method called "on_" + event_name.
        For example, on_connect will be called on event 'connect'.
        Method calls are scheduled in the async loop. wait parameter must be set to true
        to wait until all methods are completed.
        :param event_name:
        :param args:
        :param kwargs:
        :param wait: indicates if fire_event should wait for plugin calls completion (True), or not
        :return:
        """
        tasks: list[asyncio.Future[Any]] = []
        event_method_name = "on_" + event_name
        for plugin in self._plugins:
            event_method = getattr(plugin, event_method_name, None)
            if event_method:
                try:
                    task = self._schedule_coro(event_method(*args, **kwargs))
                    tasks.append(task)

                    def clean_fired_events(future: asyncio.Future[Any]) -> None:
                        with contextlib.suppress(KeyError, ValueError):
                            self._fired_events.remove(future)

                    task.add_done_callback(clean_fired_events)
                except AssertionError:
                    self.logger.exception(f"Method '{event_method_name}' on plugin '{plugin.__class__}' is not a coroutine")

        self._fired_events.extend(tasks)
        if wait and tasks:
            await asyncio.wait(tasks)
        self.logger.debug(f"Plugins len(_fired_events)={len(self._fired_events)}")

    async def map(
        self,
        coro: Callable[[Plugin, Any], Awaitable[str | bool | None]],
        *args: Any,
        **kwargs: Any,
    ) -> dict[Plugin, str | bool | None]:
        """Schedule a given coroutine call for each plugin.

        The coro called gets the Plugin instance as the first argument of its method call.
        :param coro: coro to call on each plugin
        :param filter_plugins: list of plugin names to filter (only plugin whose name is
            in the filter are called). None will call all plugins. [] will call None.
        :param args: arguments to pass to coro
        :param kwargs: arguments to pass to coro
        :return: dict containing return from coro call for each plugin.
        """
        p_list = kwargs.pop("filter_plugins", None)
        if p_list is None:
            p_list = [p.name for p in self.plugins]
        tasks: list[asyncio.Future[Any]] = []
        plugins_list: list[Plugin] = []
        for plugin in self._plugins:
            if plugin.name in p_list:
                coro_instance = coro(plugin, *args, **kwargs)
                if coro_instance:
                    try:
                        tasks.append(self._schedule_coro(coro_instance))
                        plugins_list.append(plugin)
                    except AssertionError:
                        self.logger.exception(f"Method '{coro!r}' on plugin '{plugin.name}' is not a coroutine")
        if tasks:
            ret_list = await asyncio.gather(*tasks)
            # Create result map plugin => ret
            ret_dict = dict(zip(plugins_list, ret_list, strict=False))
        else:
            ret_dict = {}
        return ret_dict

    @staticmethod
    async def _call_coro(plugin: Plugin, coro_name: str, *args: Any, **kwargs: Any) -> str | bool | None:
        if not hasattr(plugin.object, coro_name):
            _LOGGER.warning(f"Plugin doesn't implement coro_name '{coro_name}': {plugin.name}")
            return None

        coro: Awaitable[str | bool | None] = getattr(plugin.object, coro_name)(*args, **kwargs)
        return await coro

    async def map_plugin_coro(self, coro_name: str, *args: Any, **kwargs: Any) -> dict[Plugin, str | bool | None]:
        """Call a plugin declared by plugin by its name.

        :param coro_name:
        :param args:
        :param kwargs:
        :return:
        """
        return await self.map(self._call_coro, coro_name, *args, **kwargs)


    async def map_plugin_auth(self, session: Session) -> dict['BaseAuthPlugin', str | bool | None]:

        tasks: list[asyncio.Future[Any]] = []

        for plugin in self._auth_plugins:

            async def auth_coro(p: 'BaseAuthPlugin', s: Session) -> str | bool | None:
                return await p.authenticate(session=s)

            coro_instance: Awaitable[str | bool | None] =  auth_coro(plugin, session)
            tasks.append(asyncio.ensure_future(coro_instance))

        if tasks:
            ret_list = await asyncio.gather(*tasks)
            # Create result map plugin => ret
            ret_dict = dict(zip(self._auth_plugins, ret_list, strict=False))
        else:
            ret_dict = {}
        return ret_dict

    async def map_plugin_topic(self, session: Session, topic: str, action: 'Action') -> dict['BaseTopicPlugin', str | bool | None]:

        tasks: list[asyncio.Future[Any]] = []

        for plugin in self._topic_plugins:

            async def topic_coro(p: 'BaseTopicPlugin', s: Session, t: str, a: 'Action') -> str | bool | None:
                return await p.topic_filtering(session=s, topic=t, action=a)

            coro_instance: Awaitable[str | bool | None] =  topic_coro(plugin, session, topic, action)
            tasks.append(asyncio.ensure_future(coro_instance))

        if tasks:
            ret_list = await asyncio.gather(*tasks)
            # Create result map plugin => ret
            ret_dict = {dict(zip(self._auth_plugins, ret_list, strict=False))}
        else:
            ret_dict = {}
        return ret_dict
