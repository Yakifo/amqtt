from dataclasses import dataclass, field, fields, replace
import logging

try:
    from enum import Enum, StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from dacite import Config as DaciteConfig, from_dict as dict_to_dataclass

from amqtt.mqtt.constants import QOS_0, QOS_2

if TYPE_CHECKING:
    import asyncio

logger = logging.getLogger(__name__)


class BaseContext:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.logger: logging.Logger = logging.getLogger(__name__)
        # cleanup with a `Generic` type
        self.config: ClientConfig | BrokerConfig | dict[str, Any] | None = None


class Action(StrEnum):
    """Actions issued by the broker."""

    SUBSCRIBE = "subscribe"
    PUBLISH = "publish"
    RECEIVE = "receive"


class ListenerType(StrEnum):
    """Types of mqtt listeners."""

    TCP = "tcp"
    WS = "ws"
    AIOHTTP = "aiohttp"

    def __repr__(self) -> str:
        """Display the string value, instead of the enum member."""
        return f'"{self.value!s}"'

class Dictable:
    """Add dictionary methods to a dataclass."""

    def __getitem__(self, key:str) -> Any:
        """Allow dict-style `[]` access to a dataclass."""
        return self.get(key)

    def get(self, name:str, default:Any=None) -> Any:
        """Allow dict-style access to a dataclass."""
        name = name.replace("-", "_")
        if hasattr(self, name):
            return getattr(self, name)
        if default is not None:
            return default
        msg = f"'{name}' is not defined"
        raise ValueError(msg)

    def __contains__(self, name: str) -> bool:
        """Provide dict-style 'in' check."""
        return getattr(self, name.replace("-", "_"), None) is not None

    def __iter__(self) -> Iterator[Any]:
        """Provide dict-style iteration."""
        for f in fields(self):   # type: ignore[arg-type]
            yield getattr(self, f.name)

    def copy(self) -> dataclass:  # type: ignore[valid-type]
        """Return a copy of the dataclass."""
        return replace(self)  # type: ignore[type-var]

    @staticmethod
    def _coerce_lists(value: list[Any] | dict[str, Any] | Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return value  # It's already a list of dicts
        if isinstance(value, dict):
            return [value]  # Promote single dict to a list
        msg = "Could not convert 'list' to 'list[dict[str, Any]]'"
        raise ValueError(msg)


@dataclass
class ListenerConfig(Dictable):
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

    def __post_init__(self) -> None:
        """Check config for errors and transform fields for easier use."""
        if (self.certfile is None) ^ (self.keyfile is None):
            msg = "If specifying the 'certfile' or 'keyfile', both are required."
            raise ValueError(msg)

        for fn in ("cafile", "capath", "certfile", "keyfile"):
            if isinstance(getattr(self, fn), str):
                setattr(self, fn, Path(getattr(self, fn)))

    def apply(self, other: "ListenerConfig") -> None:
        """Apply the field from 'other', if 'self' field is default."""
        for f in fields(self):
            if getattr(self, f.name) == f.default:
                setattr(self, f.name, other[f.name])

def default_listeners() -> dict[str, Any]:
    """Create defaults for BrokerConfig.listeners."""
    return {
        "default": ListenerConfig()
    }

def default_broker_plugins() -> dict[str, Any]:
    """Create defaults for BrokerConfig.plugins."""
    return {
        "amqtt.plugins.logging_amqtt.EventLoggerPlugin":{},
        "amqtt.plugins.logging_amqtt.PacketLoggerPlugin":{},
        "amqtt.plugins.authentication.AnonymousAuthPlugin":{"allow_anonymous":True},
        "amqtt.plugins.sys.broker.BrokerSysPlugin":{"sys_interval":20}
    }


@dataclass
class BrokerConfig(Dictable):
    """Structured configuration for a broker. Can be passed directly to `amqtt.broker.Broker` or created from a dictionary."""

    listeners: dict[Literal["default"] | str, ListenerConfig] = field(default_factory=default_listeners) # noqa: PYI051
    """Network of listeners used by the services. a 'default' named listener is required; if another listener
     does not set a value, the 'default' settings are applied. See
     [ListenerConfig](#amqtt.contexts.ListenerConfig) for more information."""
    sys_interval: int | None = None
    """*Deprecated field to configure the `BrokerSysPlugin`. See [`BrokerSysPlugin`](#sys-topics)
    for recommended configuration.*"""
    timeout_disconnect_delay: int | None = 0
    """Client disconnect timeout without a keep-alive."""
    session_expiry_interval: int | None = None
    """Seconds for an inactive session to be retained."""
    auth: dict[str, Any] | None = None
    """*Deprecated field used to config EntryPoint-loaded plugins. See
    [`AnonymousAuthPlugin`](#anonymous-auth-plugin) and
    [`FileAuthPlugin`](#password-file-auth-plugin) for recommended configuration.*"""
    topic_check: dict[str, Any] | None = None
    """*Deprecated field used to config EntryPoint-loaded plugins. See
    [`TopicTabooPlugin`](#taboo-topic-plugin) and
    [`TopicACLPlugin`](#acl-topic-plugin) for recommended configuration method.*"""
    plugins: dict[str, Any] | list[str | dict[str,Any]] | None = field(default_factory=default_broker_plugins)
    """The dictionary has a key of the dotted-module path of a class derived from `BasePlugin`, `BaseAuthPlugin`
     or `BaseTopicPlugin`; the value is a dictionary of configuration options for that plugin. See
     [Plugins](http://localhost:8000/custom_plugins/) for more information. `list[str | dict[str,Any]]` is not
     recommended but available to support legacy use cases."""

    def __post_init__(self) -> None:
        """Check config for errors and transform fields for easier use."""
        if self.sys_interval is not None:
            logger.warning("sys_interval is deprecated, use 'plugins' to define configuration")

        if self.auth is not None or self.topic_check is not None:
            logger.warning("'auth' and 'topic-check' are deprecated, use 'plugins' to define configuration")

        default_listener = self.listeners["default"]
        for listener_name, listener in self.listeners.items():
            if listener_name == "default":
                continue
            listener.apply(default_listener)

        if isinstance(self.plugins, list):
            _plugins: dict[str, Any] = {}
            for plugin in self.plugins:
                # in case a plugin in a yaml file is listed without config map
                if isinstance(plugin, str):
                    _plugins |= {plugin:{}}
                    continue
                _plugins |= plugin
            self.plugins = _plugins

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "BrokerConfig":
        """Create a broker config from a dictionary."""
        if d is None:
            return BrokerConfig()

        # patch the incoming dictionary so it can be loaded correctly
        if "topic-check" in d:
            d["topic_check"] = d["topic-check"]
            del d["topic-check"]

        # identify EntryPoint plugin loading and prevent 'plugins' from getting defaults
        if ("auth" in d or "topic-check" in d) and "plugins" not in d:
            d["plugins"] = None

        return dict_to_dataclass(data_class=BrokerConfig,
                                 data=d,
                                 config=DaciteConfig(
                                     cast=[StrEnum, ListenerType],
                                     strict=True,
                                     type_hooks={list[dict[str, Any]]: cls._coerce_lists}
                                 ))


@dataclass
class ConnectionConfig(Dictable):
    """Properties for connecting to the broker."""

    uri: str | None = "mqtt://127.0.0.1:1883"
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
        """Check config for errors and transform fields for easier use."""
        if (self.certfile is None) ^ (self.keyfile is None):
            msg = "If specifying the 'certfile' or 'keyfile', both are required."
            raise ValueError(msg)

        for fn in ("cafile", "capath", "certfile", "keyfile"):
            if isinstance(getattr(self, fn), str):
                setattr(self, fn, Path(getattr(self, fn)))

@dataclass
class TopicConfig(Dictable):
    """Configuration of how messages to specific topics are published.

    The topic name is specified as the key in the dictionary of the `ClientConfig.topics.
    """

    qos: int = 0
    """The quality of service associated with the publishing to this topic."""
    retain: bool = False
    """Determines if the message should be retained by the topic it was published."""

    def __post__init__(self) -> None:
        """Check config for errors and transform fields for easier use."""
        if self.qos is not None and (self.qos < QOS_0 or self.qos > QOS_2):
            msg = "Topic config: default QoS must be 0, 1 or 2."
            raise ValueError(msg)


@dataclass
class WillConfig(Dictable):
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
        """Check config for errors and transform fields for easier use."""
        if self.qos is not None and (self.qos < QOS_0 or self.qos > QOS_2):
            msg = "Will config: default QoS must be 0, 1 or 2."
            raise ValueError(msg)


def default_client_plugins() -> dict[str, Any]:
    """Create defaults for `ClientConfig.plugins`."""
    return {
        "amqtt.plugins.logging_amqtt.PacketLoggerPlugin":{}
    }


@dataclass
class ClientConfig(Dictable):
    """Structured configuration for a broker. Can be passed directly to `amqtt.broker.Broker` or created from a dictionary."""

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
    plugins: dict[str, Any] | list[dict[str, Any]] | None = field(default_factory=default_client_plugins)
    """The dictionary has a key of the dotted-module path of a class derived from `BasePlugin`; the value is
     a dictionary of configuration options for that plugin. See [Plugins](http://localhost:8000/custom_plugins/)
     for more information."""
    check_hostname: bool | None = True
    """If establishing a secure connection, should the hostname of the certificate be verified."""
    will: WillConfig | None = None
    """Message, topic and flags that should be sent to if the client disconnects. See
    [WillConfig](#amqtt.contexts.WillConfig)"""

    def __post__init__(self) -> None:
        """Check config for errors and transform fields for easier use."""
        if self.default_qos is not None and (self.default_qos < QOS_0 or self.default_qos > QOS_2):
            msg = "Client config: default QoS must be 0, 1 or 2."
            raise ValueError(msg)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "ClientConfig":
        """Create a client config from a dictionary."""
        if d is None:
            return ClientConfig()

        return dict_to_dataclass(data_class=ClientConfig,
                                 data=d,
                                 config=DaciteConfig(
                                     cast=[StrEnum],
                                     strict=True)
                                 )
