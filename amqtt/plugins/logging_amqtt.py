from collections.abc import Callable, Coroutine
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from amqtt.plugins.manager import BasePlugin


if TYPE_CHECKING:
    from amqtt.session import Session


class EventLoggerPlugin(BasePlugin):
    """A plugin to log events dynamically based on method names."""

    async def log_event(self, *args: Any, **kwargs: Any) -> None:
        """Log the occurrence of an event."""
        event_name = kwargs["event_name"].replace("old", "")
        self.context.logger.info(f"### '{event_name}' EVENT FIRED ###")

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, None]]:
        """Dynamically handle calls to methods starting with 'on_'."""
        if name.startswith("on_"):
            return partial(self.log_event, event_name=name)
        msg = f"'EventLoggerPlugin' object has no attribute {name!r}"
        raise AttributeError(msg)


class PacketLoggerPlugin(BasePlugin):
    """A plugin to log MQTT packets sent and received."""

    async def on_mqtt_packet_received(self, *args: Any, **kwargs: Any) -> None:
        """Log an MQTT packet when it is received."""
        packet = kwargs.get("packet")
        session: Session | None = kwargs.get("session")
        if self.context.logger.isEnabledFor(logging.DEBUG):
            if session is not None:
                self.context.logger.debug(f"{session.client_id} <-in-- {packet!r}")
            else:
                self.context.logger.debug(f"<-in-- {packet!r}")

    async def on_mqtt_packet_sent(self, *args: Any, **kwargs: Any) -> None:
        """Log an MQTT packet when it is sent."""
        packet = kwargs.get("packet")
        session: Session | None = kwargs.get("session")
        if self.context.logger.isEnabledFor(logging.DEBUG):
            if session is not None:
                self.context.logger.debug(f"{session.client_id} -out-> {packet!r}")
            else:
                self.context.logger.debug(f"-out-> {packet!r}")
