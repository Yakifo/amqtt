from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from amqtt.adapters import ReaderAdapter, WriterAdapter
from amqtt.contexts import BaseContext
from amqtt.session import ApplicationMessage, OutgoingApplicationMessage, Session

C = TypeVar("C", bound=BaseContext)


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
    async def mqtt_disconnect(self) -> None:
        """Disconnect the protocol handler from the remote peer."""

    @abstractmethod
    async def mqtt_ping(self) -> Any:
        """Send a ping request and return the corresponding response."""

    @abstractmethod
    async def mqtt_deliver_next_message(self) -> ApplicationMessage | None:
        """Return the next application message available for delivery."""


class BrokerProtocolHandlerBase(ProtocolHandlerBase[C], ABC):
    """Abstract broker-facing protocol-handler contract."""

    @abstractmethod
    async def handle_write_timeout(self) -> None:
        """Handle a write timeout event."""

    @abstractmethod
    async def handle_read_timeout(self) -> None:
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
    async def handle_write_timeout(self) -> None:
        """Handle a write timeout event."""

    @abstractmethod
    async def handle_read_timeout(self) -> None:
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
    async def mqtt_connect(self) -> int | None:
        """Send CONNECT and await CONNACK."""

    @abstractmethod
    async def mqtt_subscribe(self, topics: list[tuple[str, int]], packet_id: int) -> list[int]:
        """Send SUBSCRIBE and await SUBACK."""

    @abstractmethod
    async def mqtt_unsubscribe(self, topics: list[str], packet_id: int) -> None:
        """Send UNSUBSCRIBE and await UNSUBACK."""
