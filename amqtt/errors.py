class AMQTTError(Exception):
    """aMQTT base exception."""


class MQTTError(Exception):
    """Base class for all errors referring to MQTT specifications."""


class CodecError(Exception):
    """Exceptions thrown by packet encode/decode functions."""


class NoDataError(Exception):
    """Exceptions thrown by packet encode/decode functions."""


class BrokerError(Exception):
    """Exceptions thrown by broker."""


class ClientError(Exception):
    """Exceptions thrown by client."""


class ConnectError(ClientError):
    """Exceptions thrown by client connect."""

    return_code: int | None = None


class ProtocolHandlerError(Exception):
    """Exceptions thrown by protocol handle."""


class PluginLoadError(Exception):
    """Exception thrown when loading a plugin."""
