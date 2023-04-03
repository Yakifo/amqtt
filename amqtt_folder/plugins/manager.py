# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

__all__ = ["get_plugin_manager", "BaseContext", "PluginManager"]

import pkg_resources
import logging
import asyncio
import copy

from collections import namedtuple


Plugin = namedtuple("Plugin", ["name", "ep", "object"])

plugins_manager = dict()


def get_plugin_manager(namespace):
    global plugins_manager
    return plugins_manager.get(namespace, None)


class BaseContext:
    def __init__(self):
        self.loop = None
        self.logger = None


class PluginManager:
    """
    Wraps setuptools Entry point mechanism to provide a basic plugin system. Plugins
    are loaded for a given namespace (group). This plugin manager uses coroutines to
    run plugin call asynchronously in an event queue
    """

    def __init__(self, namespace, context, loop=None):
        global plugins_manager
        if loop is not None:
            self._loop = loop  #Burcu: loop parametresi verildiyse 
        else:
            self._loop = asyncio.get_event_loop()  #Burcu: When called from a coroutine or a callback, this function will always return the running event loop.

        self.logger = logging.getLogger(namespace)
        if context is None:
            self.context = BaseContext()
        else:
            self.context = context
        self.context.loop = self._loop
        self._plugins = []
        self._load_plugins(namespace)
        self._fired_events = []
        plugins_manager[namespace] = self

    @property
    def app_context(self):
        return self.context

    def _load_plugins(self, namespace):
        self.logger.debug("Loading plugins for namespace %s" % namespace)
        for ep in pkg_resources.iter_entry_points(group=namespace):
            plugin = self._load_plugin(ep)
            self._plugins.append(plugin)
            self.logger.debug(" Plugin %s ready" % ep.name)

    def _load_plugin(self, ep: pkg_resources.EntryPoint):
        try:
            self.logger.debug(" Loading plugin %s" % ep)
            plugin = ep.load(require=True)
            self.logger.debug(" Initializing plugin %s" % ep)
            plugin_context = copy.copy(self.app_context)
            plugin_context.logger = self.logger.getChild(ep.name)
            obj = plugin(plugin_context)
            self.logger.debug(" ###Burcu: Loading plugin in _load_plugin %s" % ep.name)
            return Plugin(ep.name, ep, obj)
        except ImportError as ie:
            self.logger.warning(f"Plugin {ep!r} import failed: {ie}")
        except pkg_resources.UnknownExtra as ue:
            self.logger.warning(f"Plugin {ep!r} dependencies resolution failed: {ue}")

    def get_plugin(self, name):
        """
        Get a plugin by its name from the plugins loaded for the current namespace
        :param name:
        :return:
        """
        for p in self._plugins:
            if p.name == name:
                return p
        return None

    async def close(self):
        """
        Free PluginManager resources and cancel pending event methods
        This method call a close() coroutine for each plugin, allowing plugins to close
        and free resources
        :return:
        """
        await self.map_plugin_coro("close")
        for task in self._fired_events:
            task.cancel()

    @property
    def plugins(self):
        """
        Get the loaded plugins list
        :return:
        """
        return self._plugins

    def _schedule_coro(self, coro):
        return asyncio.ensure_future(coro)

    async def fire_event(self, event_name, wait=False, *args, **kwargs):
        """
        Fire an event to plugins.
        PluginManager schedule async calls for each plugin on method called "on_" + event_name
        For example, on_connect will be called on event 'connect'
        Method calls are schedule in the async loop. wait parameter must be set to true
        to wait until all methods are completed.
        :param event_name:
        :param args:
        :param kwargs:
        :param wait: indicates if fire_event should wait for plugin calls completion (True), or not
        :return:


        Burcu: event_name = connect olduğunda on_connect metodu name'ini oluşturuyor ve plugins listesinde
        event method name'i on_connect olan method bulunca onunla ilgili bir task yaratip ensure future ile çaliştiriyor ve sonra
        tasks listesine ekliyor.
        Sonra yaratilan task bitince onu fired events listesinden silebilmek için done callback fonskiyonunu tanimliyor. 
        Sonra yaratilan tasklari fired_events listesine ekliyor. Eğer parametre olarak wait = True verildiyse tüm tasklari 
        bekliyor
        """
       
        tasks = []
        event_method_name = "on_" + event_name
        self.logger.debug("###Burcu: Event method namexxxx%s" % event_method_name)
        for plugin in self._plugins:
            self.logger.debug("###Burcu: Loading plugin in fire events%s" % plugin.name)
            event_method = getattr(plugin.object, event_method_name, None)  #Burcu: getattr = get attribute 
            if event_method:
                try:
                    task = self._schedule_coro(event_method(*args, **kwargs))
                    tasks.append(task)

                    def clean_fired_events(future):
                        try:
                            self._fired_events.remove(future)
                        except (KeyError, ValueError):
                            pass

                    task.add_done_callback(clean_fired_events)
                except AssertionError:
                    self.logger.error(
                        "Method '%s' on plugin '%s' is not a coroutine"
                        % (event_method_name, plugin.name)
                    )

        self._fired_events.extend(tasks)
        if wait:
            if tasks:
                await asyncio.wait(tasks)
        self.logger.debug("Plugins len(_fired_events)=%d" % (len(self._fired_events)))

    async def map(self, coro, *args, **kwargs):
        """
        Schedule a given coroutine call for each plugin.
        The coro called get the Plugin instance as first argument of its method call
        :param coro: coro to call on each plugin
        :param filter_plugins: list of plugin names to filter (only plugin whose name is
            in filter are called).
        None will call all plugins. [] will call None.
        :param args: arguments to pass to coro
        :param kwargs: arguments to pass to coro
        :return: dict containing return from coro call for each plugin


        Burcu: plugin filtresine uyan tüm pluginler için coro instance oluşturuyor ve oluşturabilmişse tasks listesinde ekliyor.
        İlgili plugin'i de plugins_list'e ekliyor. 
        Daha sonra gather fonskiyonu ile tasks listesindeki her bir task'in return code'unu ret_list'te sakliyor. 
        Plugings_list ve ret_listi kullanarak dictionary oluşturuyor
        """
        p_list = kwargs.pop("filter_plugins", None)
        if p_list is None:
            p_list = [p.name for p in self.plugins]
        tasks = []
        plugins_list = []
        for plugin in self._plugins:
            if plugin.name in p_list:
                coro_instance = coro(plugin, *args, **kwargs)
                if coro_instance:
                    try:
                        tasks.append(self._schedule_coro(coro_instance))
                        plugins_list.append(plugin)
                    except AssertionError:
                        self.logger.error(
                            "Method '%r' on plugin '%s' is not a coroutine"
                            % (coro, plugin.name)
                        )
        if tasks:
            ret_list = await asyncio.gather(*tasks)
            #Burcu: Gather function run awaitable objects in the tasks sequence concurrently. If all awaitables are completed successfully, the result of gather is an aggregate list of returned values. The order of result values corresponds to the order of awaitables in tasks.
            # Create result map plugin=>ret
            ret_dict = {k: v for k, v in zip(plugins_list, ret_list)}
        else:
            ret_dict = {}
        return ret_dict

    @staticmethod
    async def _call_coro(plugin, coro_name, *args, **kwargs):
        if not hasattr(plugin.object, coro_name):
            # Plugin doesn't implement coro_name
            return None

        coro = getattr(plugin.object, coro_name)(*args, **kwargs)
        return await coro

    async def map_plugin_coro(self, coro_name, *args, **kwargs):
        """
        Call a plugin declared by plugin by its name
        :param coro_name:
        :param args:
        :param kwargs:
        :return:
        """
        return await self.map(self._call_coro, coro_name, *args, **kwargs)
