import inspect
from logging import getLogger
from os.path import join, dirname, isfile

import pytest

import amqtt.plugins
from glob import glob

from amqtt.plugins.manager import BaseContext

_INVALID_METHOD = "invalid_foo"
_PLUGIN = "Plugin"


class _TestContext(BaseContext):
    def __init__(self):
        super().__init__()
        self.config = {"auth": {}}
        self.logger = getLogger(__file__)


def _verify_module(module, plugin_module_name):
    if not module.__name__.startswith(plugin_module_name):
        return

    for name, clazz in inspect.getmembers(module, inspect.isclass):
        if not name.endswith(_PLUGIN) or name == _PLUGIN:
            continue

        obj = clazz(_TestContext())
        with pytest.raises(
            AttributeError,
            match=f"'{name}' object has no attribute '{_INVALID_METHOD}'",
        ):
            getattr(obj, _INVALID_METHOD)
        assert hasattr(obj, _INVALID_METHOD) is False

    for name, obj in inspect.getmembers(module, inspect.ismodule):
        _verify_module(obj, plugin_module_name)


def removesuffix(self: str, suffix: str) -> str:
    # compatibility for pre 3.9
    if suffix and self.endswith(suffix):
        return self[: -len(suffix)]
    else:
        return self[:]


def test_plugins_correct_has_attr():
    module = amqtt.plugins
    for file in glob(join(dirname(module.__file__), "**/*.py"), recursive=True):
        if not isfile(file):
            continue

        name = file.replace("/", ".")
        name = name[name.find(module.__name__) : -3]
        name = removesuffix(name, ".__init__")

        __import__(name)

    _verify_module(module, module.__name__)
