import warnings
from dataclasses import dataclass, field, fields, replace, asdict
from enum import Enum, StrEnum
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, LiteralString, Literal

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

    def __repr__(self) -> str:
        return f'"{str(self.value)}"'

class Dictable:
    def __getitem__(self, key):
        return self.get(key)

    def get(self, name, default=None):
        name = name.replace("-", "_")
        if hasattr(self, name):
            return getattr(self, name)
        if default is not None:
            return default
        raise ValueError(f"'{name}' is not defined")

    def __contains__(self, name):
        return getattr(self, name, None) is not None

    def __iter__(self):
        for field in fields(self):
            yield getattr(self, field.name)


@dataclass
class ListenerConfig:
    """Structured configuration for a broker's listeners."""
    type: ListenerType = ListenerType.TCP
    """Type of listener: `tcp` for 'mqtt' or `ws` for 'websocket' when specified in dictionary or yaml.'"""
    bind: str | None = "0.0.0.0:1883"
    """address and port for the listener to bind to"""
    max_connections: int = 0
    """max number of connections allowed for this listener"""
    ssl: bool = False
    """secured by ssl"""
    cafile: str | Path | None = None
    """Path to a file of concatenated CA certificates in PEM format. See <a href="https://docs.python.org/3/library/ssl.html#ssl-certificates">Certificates</a> for more info. """
    capath: str | Path | None = None
    """Path to a directory containing several CA certificates in PEM format, following an <a href="https://docs.openssl.org/master/man3/SSL_CTX_load_verify_locations/">OpenSSL specific layout</a>."""
    cadata: str | Path | None = None
    """Either an ASCII string of one or more PEM-encoded certificates or a bytes-like object of DER-encoded certificates."""
    certfile: str | Path | None = None
    """Full path to file in PEM format containing the certificate (as well as any number of CA certificates needed to establish the certificate's authenticity.)"""
    keyfile: str | Path | None = None
    """Full path to file in PEM format containing the private key."""

    def __post_init__(self):
        for fn in ('cafile', 'capath', 'certfile', 'keyfile'):
            if isinstance(getattr(self, fn), str):
                setattr(self, fn, Path(getattr(self, fn)))

    def apply(self, other):
        """Apply the field from 'other', if 'self' field is default."""
        if not isinstance(other, ListenerConfig):
            msg = f'cannot apply {self.__class__.__name__} to {other.__class__.__name__}'
            raise TypeError(msg)
        for f in fields(self):
            if getattr(self, f.name) == f.default:
                setattr(self, f.name, other[f.name])

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
    """Structured configuration for a broker. Can be passed directly to `amqtt.broker.Broker` or created from a dictionary."""
    listeners: dict[Literal['default'] | str, ListenerConfig] = field(default_factory=default_listeners)
    """Network of listeners used by the services. See <a href="/references/broker_config/#amqtt.contexts.ListenerConfig">ListenerConfig</a> for more information."""
    sys_interval: int | None = None
    """*Deprecated field to configure the `BrokerSysPlugin`. See [`BrokerSysPlugin`](/packaged_plugins/#sys-topics) configuration instead.*"""
    timeout_disconnect_delay: int | None = 0
    """Client disconnect timeout without a keep-alive."""
    auth: dict[str, Any] | None = None
    """*Deprecated field used to config EntryPoint-loaded plugins. See [`AnonymousAuthPlugin`](/packaged_plugins/#anonymous-auth-plugin) or [`FileAuthPlugin`](/packaged_plugins/#password-file-auth-plugin) for more information.*"""
    topic_check: dict[str, Any] | None = None
    """Deprecated field used to config EntryPoint-loaded plugins. See [`TopicTabooPlugin`](/packaged_plugins/#taboo-topic-plugin) and [`TopicACLPlugin`](/packaged_plugins/#acl-topic-plugin) for more information.*"""
    plugins: dict | list[dict] | None = field(default_factory=default_broker_plugins)
    """The dictionary is the representing the modules and class name of `BasePlugin`, `BaseAuthPlugin` and `BaseTopicPlugins`; the value is a dictionary of configuration options. """

    def __post__init__(self) -> None:
        if self.sys_interval is not None:
            warnings.warn("sys_interval is deprecated, use 'plugins' to define configuration",
                          DeprecationWarning, stacklevel=1)

        if self.auth is not None or self.topic_check is not None:
            warnings.warn("'auth' and 'topic-check' are deprecated, use 'plugins' to define configuration",
                          DeprecationWarning, stacklevel=1)

        default_listener = self.listeners['default']
        for listener_name, listener in self.listeners.items():
            if listener_name == 'default':
                continue
            listener.apply(default_listener)

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
