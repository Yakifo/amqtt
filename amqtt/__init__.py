"""INIT."""

__version__ = "0.11.0"

from enum import StrEnum


class Events(StrEnum):
    """Class for all events."""

class ClientEvents(Events):
    """Events issued by the client."""


class BrokerEvents(Events):
    """Events issued by the broker."""

    PRE_START = "broker_pre_start"
    POST_START = "broker_post_start"
    PRE_SHUTDOWN = "broker_pre_shutdown"
    POST_SHUTDOWN = "broker_post_shutdown"
    CLIENT_CONNECTED = "broker_client_connected"
    CLIENT_DISCONNECTED = "broker_client_disconnected"
    CLIENT_SUBSCRIBED = "broker_client_subscribed"
    CLIENT_UNSUBSCRIBED = "broker_client_unsubscribed"
    MESSAGE_RECEIVED = "broker_message_received"
