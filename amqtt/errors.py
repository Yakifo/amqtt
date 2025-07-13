from typing import Any


class AMQTTError(Exception):
    """aMQTT base exception."""


class MQTTError(Exception):
    """Base class for all errors referring to MQTT specifications."""


class CodecError(Exception):
    """Exceptions thrown by packet encode/decode functions."""


class NoDataError(Exception):
    """Exceptions thrown by packet encode/decode functions."""

class ZeroLengthReadError(NoDataError):
    def __init__(self) -> None:
        super().__init__("Decoding a string of length zero.")

class BrokerError(Exception):
    """Exceptions thrown by broker."""


class PluginError(Exception):
    """Exceptions thrown when loading or initializing a plugin."""


class PluginImportError(PluginError):
    """Exceptions thrown when loading plugin."""


class PluginCoroError(PluginError):
    """Exceptions thrown when loading a plugin with a non-async call method."""


class PluginInitError(PluginError):
    """Exceptions thrown when initializing plugin."""

    def __init__(self, plugin: Any) -> None:
        super().__init__(f"Plugin init failed: {plugin!r}")


class ClientError(Exception):
    """Exceptions thrown by client."""


class ConnectError(ClientError):
    """Exceptions thrown by client connect."""

    return_code: int | None = None


class ProtocolHandlerError(Exception):
    """Exceptions thrown by protocol handle."""


class PluginLoadError(Exception):
    """Exception thrown when loading a plugin."""
