import warnings
from dataclasses import dataclass, field, fields, replace, asdict
from enum import Enum, StrEnum
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, LiteralString, Literal

from amqtt.mqtt.constants import QOS_0, QOS_2

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
    """Path to a file of concatenated CA certificates in PEM format. See
    [Certificates](https://docs.python.org/3/library/ssl.html#ssl-certificates) for more info."""
    capath: str | Path | None = None
    """Path to a directory containing one or more CA certificates in PEM format, following the
     [OpenSSL-specific layout](https://docs.openssl.org/master/man3/SSL_CTX_load_verify_locations/)."""
    cadata: str | Path | None = None
    """Either an ASCII string of one or more PEM-encoded certificates or a bytes-like object of DER-encoded certificates."""
    certfile: str | Path | None = None
    """Full path to file in PEM format containing the server's certificate (as well as any number of CA
    certificates needed to establish the certificate's authenticity.)"""
    keyfile: str | Path | None = None
    """Full path to file in PEM format containing the server's private key."""

    def __post_init__(self):
        if (self.certfile is None) ^ (self.keyfile is None):
            msg = "If specifying the 'certfile' or 'keyfile', both are required."
            raise ValueError(msg)

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
    """Network of listeners used by the services. a 'default' named listener is required; if another listener
     does not set a value, the 'default' settings are applied. See
     [ListenerConfig](#amqtt.contexts.ListenerConfig) for more information."""
    sys_interval: int | None = None
    """*Deprecated field to configure the `BrokerSysPlugin`. See [`BrokerSysPlugin`](../packaged_plugins.md/#sys-topics) 
    configuration instead.*"""
    timeout_disconnect_delay: int | None = 0
    """Client disconnect timeout without a keep-alive."""
    auth: dict[str, Any] | None = None
    """*Deprecated field used to config EntryPoint-loaded plugins. See 
    [`AnonymousAuthPlugin`](#anonymous-auth-plugin) and 
    [`FileAuthPlugin`](/packaged_plugins/#password-file-auth-plugin) for more information.*"""
    topic_check: dict[str, Any] | None = None
    """Deprecated field used to config EntryPoint-loaded plugins. See 
    [`TopicTabooPlugin`](#taboo-topic-plugin) and
    [`TopicACLPlugin`](#acl-topic-plugin) for more information.*"""
    plugins: dict | list[dict] | None = field(default_factory=default_broker_plugins)
    """The dictionary has a key of the dotted-module path of a class derived from `BasePlugin`, `BaseAuthPlugin`
     or `BaseTopicPlugin`; the value is a dictionary of configuration options for that plugin. See 
     [Plugins](http://localhost:8000/custom_plugins/) for more information."""

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
    """URI of the broker"""
    cafile: str | Path | None = None
    """Path to a file of concatenated CA certificates in PEM format to verify broker's authenticity. See
    [Certificates](https://docs.python.org/3/library/ssl.html#ssl-certificates) for more info."""
    capath: str | Path | None = None
    """Path to a directory containing one or more CA certificates in PEM format, following the
     [OpenSSL-specific layout](https://docs.openssl.org/master/man3/SSL_CTX_load_verify_locations/)."""
    cadata: str | None = None
    """The certificate to verify the broker's authenticity in an ASCII string format of one or more PEM-encoded
    certificates or a bytes-like object of DER-encoded certificates."""
    certfile: str | Path | None = None
    """Full path to file in PEM format containing the client's certificate (as well as any number of CA
        certificates needed to establish the certificate's authenticity.)"""
    keyfile: str | Path | None = None
    """Full path to file in PEM format containing the client's private key associated with the certfile."""

    def __post__init__(self) -> None:
        if (self.certfile is None) ^ (self.keyfile is None):
            msg = "If specifying the 'certfile' or 'keyfile', both are required."
            raise ValueError(msg)

        for fn in ('cafile', 'capath', 'certfile', 'keyfile'):
            if isinstance(getattr(self, fn), str):
                setattr(self, fn, Path(getattr(self, fn)))

@dataclass
class TopicConfig:
    """Configuration of how messages to specific topics are published. The topic name is
    specified as the key in the dictionary of the `ClientConfig.topics."""
    qos: int = 0
    """The quality of service associated with the publishing to this topic."""
    retain: bool = False
    """Determines if the message should be retained by the topic it was published."""

    def __post__init__(self) -> None:
        if self.qos is not None and (self.qos < QOS_0 or self.qos > QOS_2):
            msg = "Topic config: default QoS must be 0, 1 or 2."
            raise ValueError(msg)


@dataclass
class WillConfig:
    """Configuration of the 'last will & testament' of the client upon improper disconnection."""

    topic: str
    """The will message will be published to this topic."""
    message: str
    """The contents of the message to be published."""
    qos: int | None = QOS_0
    """The quality of service associated with sending this message."""
    retain: bool | None = False
    """Determines if the message should be retained by the topic it was published."""

    def __post__init__(self) -> None:
        if self.qos is not None and (self.qos < QOS_0 or self.qos > QOS_2):
            msg = "Will config: default QoS must be 0, 1 or 2."
            raise ValueError(msg)


def default_client_plugins():
    return {
        'amqtt.plugins.logging_amqtt.PacketLoggerPlugin':{}
    }


@dataclass
class ClientConfig(Dictable):
    keep_alive: int | None = 10
    """Keep-alive timeout sent to the broker."""
    ping_delay: int | None = 1
    """Auto-ping delay before keep-alive timeout. Setting to 0 will disable which may lead to broker disconnection."""
    default_qos: int | None = QOS_0
    """Default QoS for messages published."""
    default_retain: bool | None = False
    """Default retain value to messages published."""
    auto_reconnect: bool | None = True
    """Enable or disable auto-reconnect if connection with the broker is interrupted."""
    connection_timeout: int | None = 60
    """The number of seconds before a connection times out"""
    reconnect_retries: int | None = 2
    """Number of reconnection retry attempts. Negative value will cause client to reconnect indefinitely."""
    reconnect_max_interval: int | None = 10
    """Maximum seconds to wait before retrying a connection."""
    cleansession: bool | None = True
    """Upon reconnect, should subscriptions be cleared. Can be overridden by `MQTTClient.connect`"""
    topics: dict[str, TopicConfig] | None = field(default_factory=dict)
    """Specify the topics and what flags should be set for messages published to them."""
    broker: ConnectionConfig | None = field(default_factory=ConnectionConfig)
    """Configuration for connecting to the broker. See
     [ConnectionConfig](#amqtt.contexts.ConnectionConfig) for more information."""
    plugins: dict | list | None = field(default_factory=default_client_plugins)
    """The dictionary has a key of the dotted-module path of a class derived from `BasePlugin`; the value is
     a dictionary of configuration options for that plugin. See [Plugins](http://localhost:8000/custom_plugins/)
     for more information."""
    check_hostname: bool | None = True
    """If establishing a secure connection, should the hostname of the certificate be verified."""
    will: WillConfig | None = None
    """Message, topic and flags that should be sent to if the client disconnects. See
    [WillConfig](#amqtt.contexts.WillConfig)"""

    def __post__init__(self) -> None:
        if self.default_qos is not None and (self.default_qos < QOS_0 or self.default_qos > QOS_2):
            msg = "Client config: default QoS must be 0, 1 or 2."
            raise ValueError(msg)

