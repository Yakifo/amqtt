class AMQTTException(Exception):  # noqa: N818
    """aMQTT base exception."""


class MQTTException(Exception):  # noqa: N818
    """Base class for all errors referring to MQTT specifications."""


class CodecException(Exception):  # noqa: N818
    """Exceptions thrown by packet encode/decode functions."""


class NoDataException(Exception):  # noqa: N818
    """Exceptions thrown by packet encode/decode functions."""


class BrokerException(Exception):  # noqa: N818
    """Exceptions thrown by broker."""


class ClientException(Exception):  # noqa: N818
    """Exceptions thrown by client."""


class ConnectException(ClientException):
    """Exceptions thrown by client connect."""

    return_code: int | None = None


class ProtocolHandlerException(Exception):  # noqa: N818
    """Exceptions thrown by protocol handle."""
