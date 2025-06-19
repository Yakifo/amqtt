try:
    from enum import StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass


class Events(StrEnum):
    """Class for all events."""


class ClientEvents(Events):
    """Events issued by the client."""


class MQTTEvents(Events):
    PACKET_SENT = "mqtt_packet_sent"
    PACKET_RECEIVED = "mqtt_packet_received"


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
