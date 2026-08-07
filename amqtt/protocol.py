from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from amqtt.contexts import BaseContext

if TYPE_CHECKING:
    from amqtt.adapters import ReaderAdapter, WriterAdapter
    from amqtt.session import ApplicationMessage, OutgoingApplicationMessage, Session

C = TypeVar("C", bound=BaseContext)


@dataclass(slots=True)
class ClientDisconnect:
    """Protocol-neutral broker view of a client disconnect."""

    is_clean: bool
    packet: Any | None = None


@dataclass(frozen=True, slots=True)
class SubscriptionTopic:
    """Protocol-neutral topic subscription request."""

    topic_filter: str
    qos: int
    no_local: bool = False
    retain_as_published: bool = False
    retain_handling: int = 0
    subscription_identifier: int | None = None


@dataclass(slots=True)
class SubscriptionRequest:
    """Protocol-neutral subscription request received by the broker."""

    packet_id: int
    topics: list[SubscriptionTopic]
    properties: Any | None = None


@dataclass(slots=True)
class UnsubscriptionRequest:
    """Protocol-neutral unsubscription request received by the broker."""

    packet_id: int
    topics: list[str]
    properties: Any | None = None


class ProtocolHandlerBase(ABC, Generic[C]):
    """Abstract protocol-handler contract shared by MQTT 3.1.1 and MQTT 5.0 handlers."""

    @abstractmethod
    async def start(self) -> None:
        """Start the protocol handler."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the protocol handler."""

    @abstractmethod
    def attach(self, session: Session, reader: ReaderAdapter, writer: WriterAdapter) -> None:
        """Attach the handler to a session and transport."""

    @abstractmethod
    def detach(self) -> None:
        """Detach the handler from its current session and transport."""

    @abstractmethod
    async def mqtt_publish(
        self,
        topic: str,
        data: bytes | bytearray,
        qos: int | None,
        retain: bool,
        ack_timeout: int | None = None,
    ) -> OutgoingApplicationMessage:
        """Send a publish message through the protocol implementation."""

    @abstractmethod
    async def mqtt_deliver_next_message(self) -> ApplicationMessage | None:
        """Return the next application message available for delivery."""


class BrokerProtocolHandlerBase(ProtocolHandlerBase[C], ABC):
    """Abstract broker-facing protocol-handler contract."""

    @abstractmethod
    def handle_write_timeout(self) -> None:
        """Handle a write timeout event."""

    @abstractmethod
    def handle_read_timeout(self) -> None:
        """Handle a read timeout event."""

    @abstractmethod
    async def handle_connect(self, connect: Any) -> None:
        """Handle an inbound CONNECT packet."""

    @abstractmethod
    async def handle_pingreq(self, pingreq: Any) -> None:
        """Handle an inbound PINGREQ packet."""

    @abstractmethod
    async def handle_subscribe(self, subscribe: Any) -> None:
        """Handle an inbound SUBSCRIBE packet."""

    @abstractmethod
    async def handle_unsubscribe(self, unsubscribe: Any) -> None:
        """Handle an inbound UNSUBSCRIBE packet."""

    @abstractmethod
    async def handle_disconnect(self, disconnect: Any) -> None:
        """Handle an inbound DISCONNECT packet."""

    @abstractmethod
    async def handle_connection_closed(self) -> None:
        """Handle connection closure."""

    @abstractmethod
    async def wait_disconnect(self) -> ClientDisconnect | None:
        """Wait for a client disconnect event."""

    @abstractmethod
    async def get_next_pending_subscription(self) -> SubscriptionRequest:
        """Return the next pending broker subscription request."""

    @abstractmethod
    async def get_next_pending_unsubscription(self) -> UnsubscriptionRequest:
        """Return the next pending broker unsubscription request."""

    @abstractmethod
    async def mqtt_acknowledge_subscription(self, packet_id: int, return_codes: list[int]) -> None:
        """Send a subscription acknowledgement to the peer."""

    @abstractmethod
    async def mqtt_acknowledge_unsubscription(self, packet_id: int) -> None:
        """Send an unsubscription acknowledgement to the peer."""

    @abstractmethod
    async def mqtt_connack_authorize(self, authorize: bool) -> None:
        """Send a CONNACK response based on broker authorization."""


class ClientProtocolHandlerBase(ProtocolHandlerBase[C], ABC):
    """Abstract client-facing protocol-handler contract."""

    @abstractmethod
    def handle_write_timeout(self) -> None:
        """Handle a write timeout event."""

    @abstractmethod
    def handle_read_timeout(self) -> None:
        """Handle a read timeout event."""

    @abstractmethod
    async def handle_connack(self, connack: Any) -> None:
        """Handle an inbound CONNACK packet."""

    @abstractmethod
    async def handle_suback(self, suback: Any) -> None:
        """Handle an inbound SUBACK packet."""

    @abstractmethod
    async def handle_unsuback(self, unsuback: Any) -> None:
        """Handle an inbound UNSUBACK packet."""

    @abstractmethod
    async def handle_pingresp(self, pingresp: Any) -> None:
        """Handle an inbound PINGRESP packet."""

    @abstractmethod
    async def handle_connection_closed(self) -> None:
        """Handle connection closure."""

    @abstractmethod
    async def wait_disconnect(self) -> None:
        """Wait for a server disconnect event."""

    @abstractmethod
    async def mqtt_connect(self) -> int | None:
        """Send CONNECT and await CONNACK."""

    @abstractmethod
    async def mqtt_disconnect(self) -> None:
        """Disconnect the protocol handler from the remote peer."""

    @abstractmethod
    async def mqtt_ping(self) -> Any:
        """Send a ping request and return the corresponding response."""

    @abstractmethod
    async def mqtt_subscribe(self, topics: list[tuple[str, int]], packet_id: int) -> list[int]:
        """Send SUBSCRIBE and await SUBACK."""

    @abstractmethod
    async def mqtt_unsubscribe(self, topics: list[str], packet_id: int) -> None:
        """Send UNSUBSCRIBE and await UNSUBACK."""
