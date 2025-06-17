from collections.abc import Callable, Coroutine
from functools import partial
import logging
from typing import Any, TypeAlias

from amqtt.events import BrokerEvents
from amqtt.mqtt import MQTTPacket
from amqtt.mqtt.packet import MQTTFixedHeader, MQTTPayload, MQTTVariableHeader
from amqtt.plugins.base import BasePlugin
from amqtt.plugins.manager import BaseContext
from amqtt.session import Session

PACKET: TypeAlias = MQTTPacket[MQTTVariableHeader, MQTTPayload[MQTTVariableHeader], MQTTFixedHeader]


class EventLoggerPlugin(BasePlugin[BaseContext]):
    """A plugin to log events dynamically based on method names."""

    async def log_event(self, *args: Any, **kwargs: Any) -> None:
        """Log the occurrence of an event."""
        event_name = kwargs["event_name"].replace("old", "")
        if event_name.replace("on_", "") in (BrokerEvents.CLIENT_CONNECTED, BrokerEvents.CLIENT_DISCONNECTED):
            self.context.logger.info(f"### '{event_name}' EVENT FIRED ###")
        else:
            self.context.logger.debug(f"### '{event_name}' EVENT FIRED ###")

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, None]]:
        """Dynamically handle calls to methods starting with 'on_'."""
        if name.startswith("on_"):
            return partial(self.log_event, event_name=name)
        msg = f"'EventLoggerPlugin' object has no attribute {name!r}"
        raise AttributeError(msg)


class PacketLoggerPlugin(BasePlugin[BaseContext]):
    """A plugin to log MQTT packets sent and received."""

    async def on_mqtt_packet_received(self, *, packet: PACKET, session: Session | None = None) -> None:
        """Log an MQTT packet when it is received."""
        if self.context.logger.isEnabledFor(logging.DEBUG):
            if session is not None:
                self.context.logger.debug(f"{session.client_id} <-in-- {packet!r}")
            else:
                self.context.logger.debug(f"<-in-- {packet!r}")

    async def on_mqtt_packet_sent(self, *, packet: PACKET, session: Session | None = None) -> None:
        """Log an MQTT packet when it is sent."""
        if self.context.logger.isEnabledFor(logging.DEBUG):
            if session is not None:
                self.context.logger.debug(f"{session.client_id} -out-> {packet!r}")
            else:
                self.context.logger.debug(f"-out-> {packet!r}")
