import warnings
from dataclasses import dataclass, field, fields, replace, asdict
from enum import Enum, StrEnum
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from amqtt.mqtt.constants import QOS_0

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    import asyncio


class BaseContext:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.logger: logging.Logger = _LOGGER
        self.config: dict[str, Any] | None = None


class Action(Enum):
    """Actions issued by the broker."""

    SUBSCRIBE = "subscribe"
    PUBLISH = "publish"


class ListenerType(StrEnum):
    TCP = 'tcp'
    WS = 'ws'


class Dictable:
    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, name, default=None):
        if hasattr(self, name):
            return getattr(self, name)
        if default is not None:
            return default
        raise ValueError(f"'{name}' is not defined")

    def copy(self):
        return replace(self)

    def update(self, other):
        if not isinstance(other, self.__class__):
            raise TypeError(f'must update with another {self.__class__.__name__}')
        for f in fields(self):
            if isinstance(getattr(self, f.name), Dictable):
                setattr(self, f.name, getattr(self, f.name).update(getattr(other, f.name)))
            if getattr(self, f.name) == f.default:
                setattr(self, f.name, other[f.name])

        # if not isinstance(other, self.__class__):
        #     raise TypeError(f'must update with another {self.__class__.__name__}')
        #
        # valids = { k:v for k,v in asdict(self).items() if v is not None }
        # return replace(other, **valids)

    def __ior__(self, other):
        self.update(other)
        return self
        # if not isinstance(other, self.__class__):
        #     raise TypeError(f'must update with another {self.__class__.__name__}')
        # for f in fields(self):
        #     if getattr(self, f.name) == f.default:
        #         setattr(self, f.name, other[f.name])
        # return self

    def __contains__(self, name):
        return getattr(self, name, None) is not None

    def __iter__(self):
        for field in fields(self):
            yield getattr(self, field.name)


@dataclass
class ListenerConfig(Dictable):
    type: ListenerType = ListenerType.TCP
    bind: str | None = "0.0.0.0:1883"
    max_connections: int = 0
    ssl: bool = False
    cafile: str | Path | None = None
    capath: str | Path | None = None
    cadata: str | Path | None = None
    certfile: str | Path | None = None
    keyfile: str | Path | None = None

    def __post_init__(self):
        for fn in ('cafile', 'capath', 'certfile', 'keyfile'):
            if isinstance(getattr(self, fn), str):
                setattr(self, fn, Path(getattr(self, fn)))

def default_listeners():
    return {
        'default': ListenerConfig()
    }

def default_broker_plugins():
    return {
        'amqtt.plugins.logging_amqtt.EventLoggerPlugin':{},
        'amqtt.plugins.logging_amqtt.PacketLoggerPlugin':{},
        'amqtt.plugins.authentication.AnonymousAuthPlugin':{'allow_anonymous':True},
        'amqtt.plugins.sys.broker.BrokerSysPlugin':{'sys_interval':20}
    }


@dataclass
class BrokerConfig(Dictable):
    listeners: dict[str, ListenerConfig] = field(default_factory=dict)
    sys_interval: int | None = None
    timeout_disconnect_delay: int | None = 0
    plugins: dict | list | None = None
    auth: dict[str, Any] | None = None
    topic_check: dict[str, Any] | None = None

    def __post__init__(self) -> None:
        if self.sys_interval is not None:
            warnings.warn("sys_interval is deprecated, use 'plugins' to define configuration",
                          DeprecationWarning, stacklevel=1)

        if self.auth is not None or self.topic_check is not None:
            warnings.warn("'auth' and 'topic-check' are deprecated, use 'plugins' to define configuration",
                          DeprecationWarning, stacklevel=1)

        default_listener = self.listeners['default']
        for listener_name, listener in self.listeners.items():
            listener.update(default_listener)

        if isinstance(self.plugins, list):
            _plugins = {}
            for plugin in self.plugins:
                _plugins |= plugin
            self.plugins = _plugins


@dataclass
class ConnectionConfig(Dictable):
    uri: str | None = "mqtt://127.0.0.1"
    cafile: str | Path | None = None
    capath: str | Path | None = None
    cadata: str | None = None
    certfile: str | Path | None = None
    keyfile: str | Path | None = None


class TopicConfig:
    qos: int = 0
    retain: bool = False


def default_client_plugins():
    return {
        'amqtt.plugins.logging_amqtt.PacketLoggerPlugin':{}
    }


@dataclass
class ClientConfig(Dictable):
    keep_alive: int | None = 10
    ping_delay: int | None = 1
    default_qos: int | None = QOS_0
    default_retain: bool | None = False
    auto_reconnect: bool | None = True
    connection_timeout: int | None = 60
    reconnect_retries: int | None = 2
    reconnect_max_interval: int | None = 10
    cleansession: bool | None = True
    topics: dict[str, TopicConfig] | None = field(default_factory=dict)
    broker: ConnectionConfig | None = field(default_factory=ConnectionConfig)
    plugins: dict | list | None = field(default_factory=default_client_plugins)
    check_hostname: bool | None = True
