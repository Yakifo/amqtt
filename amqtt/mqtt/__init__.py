# Back-compat shim for ....<parent>.mqtt -> ....<parent>.mqtt3
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import warnings

# Compute names based on where this package is nested
PKG = __name__  # e.g. "amqtt.mqtt" or just "mqtt"
PARENT = PKG.rsplit(".", 1)[0] if "." in PKG else None
TARGET_ROOT = (PARENT + ".mqtt3") if PARENT else "mqtt3"  # e.g. "amqtt.mqtt3"

warnings.warn(
    f"The '{PKG}' package is deprecated; use '{TARGET_ROOT}' instead.",
    DeprecationWarning,
    stacklevel=2,
)


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, alias_name: str, target_name: str):
        self.alias_name = alias_name
        self.target_name = target_name

    def create_module(self, spec):
        mod = importlib.import_module(self.target_name)
        sys.modules[self.alias_name] = mod
        return mod

    def exec_module(self, module):
        return


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        # Only handle submodules under this package (e.g. "amqtt.mqtt.*")
        if fullname == PKG or not fullname.startswith(PKG + "."):
            return None

        # Map "amqtt.mqtt.foo.bar" -> "amqtt.mqtt3.foo.bar"
        suffix = fullname[len(PKG):]  # ".foo.bar"
        target_name = TARGET_ROOT + suffix

        real_spec = importlib.util.find_spec(target_name)
        if real_spec is None:
            return None

        is_pkg = real_spec.submodule_search_locations is not None
        spec = importlib.machinery.ModuleSpec(
            name=fullname,
            loader=_AliasLoader(alias_name=fullname, target_name=target_name),
            origin=f"alias-of:{target_name}",
            is_package=is_pkg,
        )
        if is_pkg:
            spec.submodule_search_locations = []  # allow nested imports under the alias
        return spec


# Install finder once
if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())


# Support attribute access: from amqtt.mqtt import constants
def __getattr__(name):
    target = f"{TARGET_ROOT}.{name}"
    try:
        mod = importlib.import_module(target)
    except ModuleNotFoundError as e:
        raise AttributeError(name) from e
    sys.modules[f"{PKG}.{name}"] = mod
    return mod


# ---- existing finder code above stays the same ----

# Proxy attributes defined in the target root package (e.g., amqtt.mqtt3)
import importlib

_target_pkg = None


def _get_target_pkg():
    global _target_pkg
    if _target_pkg is None:
        _target_pkg = importlib.import_module(TARGET_ROOT)
    return _target_pkg


def __getattr__(name):
    # 1) If the name is an attribute on the target root package, return it
    tp = _get_target_pkg()
    if hasattr(tp, name):
        return getattr(tp, name)

    # 2) Otherwise try to treat it as a submodule and load it lazily
    target = f"{TARGET_ROOT}.{name}"
    try:
        mod = importlib.import_module(target)
    except ModuleNotFoundError as e:
        raise AttributeError(name) from e
    sys.modules[f"{PKG}.{name}"] = mod
    return mod


def __dir__():
    # Make dir() and auto-complete show names from the target package
    tp = _get_target_pkg()
    try:
        return sorted(set(globals().keys()) | set(dir(tp)))
    except Exception:
        return sorted(globals().keys())


# Make star-imports behave sensibly
try:
    __all__ = list(getattr(_get_target_pkg(), "__all__", []))
except Exception:
    __all__ = []
