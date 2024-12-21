# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.


from functools import partial
import logging


class EventLoggerPlugin:
    def __init__(self, context) -> None:
        self.context = context

    async def log_event(self, *args, **kwargs) -> None:
        self.context.logger.info(
            "### '{}' EVENT FIRED ###".format(kwargs["event_name"].replace("old", "")),
        )

    def __getattr__(self, name):
        if name.startswith("on_"):
            return partial(self.log_event, event_name=name)
        msg = f"'EventLoggerPlugin' object has no attribute {name!r}"
        raise AttributeError(msg)


class PacketLoggerPlugin:
    def __init__(self, context) -> None:
        self.context = context

    async def on_mqtt_packet_received(self, *args, **kwargs) -> None:
        packet = kwargs.get("packet")
        session = kwargs.get("session")
        if self.context.logger.isEnabledFor(logging.DEBUG):
            if session:
                self.context.logger.debug(
                    f"{session.client_id} <-in-- {packet!r}",
                )
            else:
                self.context.logger.debug(f"<-in-- {packet!r}")

    async def on_mqtt_packet_sent(self, *args, **kwargs) -> None:
        packet = kwargs.get("packet")
        session = kwargs.get("session")
        if self.context.logger.isEnabledFor(logging.DEBUG):
            if session:
                self.context.logger.debug(
                    f"{session.client_id} -out-> {packet!r}",
                )
            else:
                self.context.logger.debug(f"-out-> {packet!r}")
