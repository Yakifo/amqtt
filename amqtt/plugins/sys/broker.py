import asyncio
from collections import deque  # pylint: disable=C0412
from typing import SupportsIndex, SupportsInt, TypeAlias  # pylint: disable=C0412

from amqtt.plugins.base import BasePlugin
from amqtt.session import Session

try:
    from collections.abc import Buffer
except ImportError:
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class Buffer(Protocol):  #  type: ignore[no-redef]
        def __buffer__(self, flags: int = ...) -> memoryview:
            """Mimic the behavior of `collections.abc.Buffer` for python 3.10-3.12."""


try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc


import amqtt
from amqtt.broker import BrokerContext
from amqtt.codecs_amqtt import int_to_bytes_str
from amqtt.mqtt.packet import PUBLISH, MQTTFixedHeader, MQTTPacket, MQTTPayload, MQTTVariableHeader

DOLLAR_SYS_ROOT = "$SYS/broker/"
STAT_BYTES_SENT = "bytes_sent"
STAT_BYTES_RECEIVED = "bytes_received"
STAT_MSG_SENT = "messages_sent"
STAT_MSG_RECEIVED = "messages_received"
STAT_PUBLISH_SENT = "publish_sent"
STAT_PUBLISH_RECEIVED = "publish_received"
STAT_START_TIME = "start_time"
STAT_CLIENTS_MAXIMUM = "clients_maximum"
STAT_CLIENTS_CONNECTED = "clients_connected"
STAT_CLIENTS_DISCONNECTED = "clients_disconnected"


PACKET: TypeAlias = MQTTPacket[MQTTVariableHeader, MQTTPayload[MQTTVariableHeader], MQTTFixedHeader]


class BrokerSysPlugin(BasePlugin[BrokerContext]):
    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        # Broker statistics initialization
        self._stats: dict[str, int] = {}
        self._sys_handle: asyncio.Handle | None = None

    def _clear_stats(self) -> None:
        """Initialize broker statistics data structures."""
        for stat in (
            STAT_BYTES_RECEIVED,
            STAT_BYTES_SENT,
            STAT_MSG_RECEIVED,
            STAT_MSG_SENT,
            STAT_CLIENTS_MAXIMUM,
            STAT_CLIENTS_CONNECTED,
            STAT_CLIENTS_DISCONNECTED,
            STAT_PUBLISH_RECEIVED,
            STAT_PUBLISH_SENT,
        ):
            self._stats[stat] = 0

    async def _broadcast_sys_topic(self, topic_basename: str, data: bytes) -> None:
        """Broadcast a system topic."""
        await self.context.broadcast_message(topic_basename, data)

    def schedule_broadcast_sys_topic(self, topic_basename: str, data: bytes) -> asyncio.Task[None]:
        """Schedule broadcasting of system topics."""
        return asyncio.ensure_future(
            self._broadcast_sys_topic(DOLLAR_SYS_ROOT + topic_basename, data),
            loop=self.context.loop,
        )

    async def on_broker_pre_start(self) -> None:
        """Clear statistics before broker start."""
        self._clear_stats()

    async def on_broker_post_start(self) -> None:
        """Initialize statistics and start $SYS broadcasting."""
        self._stats[STAT_START_TIME] = int(datetime.now(tz=UTC).timestamp())
        version = f"aMQTT version {amqtt.__version__}"
        self.context.retain_message(DOLLAR_SYS_ROOT + "version", version.encode())

        # Start $SYS topics management
        try:
            sys_interval: int = 0
            x = self.context.config.get("sys_interval") if self.context.config is not None else None
            if isinstance(x, str | Buffer | SupportsInt | SupportsIndex):
                sys_interval = int(x)
            if sys_interval > 0:
                self.context.logger.debug(f"Setup $SYS broadcasting every {sys_interval} seconds")
                self._sys_handle = (
                    self.context.loop.call_later(sys_interval, self.broadcast_dollar_sys_topics)
                    if self.context.loop is not None
                    else None
                )
            else:
                self.context.logger.debug("$SYS disabled")
        except KeyError:
            pass
            # 'sys_interval' config parameter not found

    async def on_broker_pre_shutdown(self) -> None:
        """Stop $SYS topics broadcasting."""
        if self._sys_handle:
            self._sys_handle.cancel()

    def broadcast_dollar_sys_topics(self) -> None:
        """Broadcast dynamic $SYS topics updates and reschedule next execution."""
        # Update stats
        uptime = int(datetime.now(tz=UTC).timestamp()) - self._stats[STAT_START_TIME]
        client_connected = self._stats[STAT_CLIENTS_CONNECTED]
        client_disconnected = self._stats[STAT_CLIENTS_DISCONNECTED]
        inflight_in = 0
        inflight_out = 0
        messages_stored = 0
        for session in self.context.sessions:
            inflight_in += session.inflight_in_count
            inflight_out += session.inflight_out_count
            messages_stored += session.retained_messages_count
        messages_stored += len(self.context.retained_messages)
        subscriptions_count = sum(len(sub) for sub in self.context.subscriptions.values())

        # Broadcast updates
        tasks: deque[asyncio.Task[None]] = deque()
        stats: dict[str, int | str] = {
            "load/bytes/received": self._stats[STAT_BYTES_RECEIVED],
            "load/bytes/sent": self._stats[STAT_BYTES_SENT],
            "messages/received": self._stats[STAT_MSG_RECEIVED],
            "messages/sent": self._stats[STAT_MSG_SENT],
            "time": int(datetime.now(tz=UTC).timestamp()),
            "uptime": str(uptime),
            "uptime/formatted": str(datetime.fromtimestamp(self._stats[STAT_START_TIME], UTC)),
            "clients/connected": client_connected,
            "clients/disconnected": client_disconnected,
            "clients/maximum": self._stats[STAT_CLIENTS_MAXIMUM],
            "clients/total": client_connected + client_disconnected,
            "messages/inflight": inflight_in + inflight_out,
            "messages/inflight/in": inflight_in,
            "messages/inflight/out": inflight_out,
            "messages/inflight/stored": messages_stored,
            "messages/publish/received": self._stats[STAT_PUBLISH_RECEIVED],
            "messages/publish/sent": self._stats[STAT_PUBLISH_SENT],
            "messages/retained/count": len(self.context.retained_messages),
            "messages/subscriptions/count": subscriptions_count,
        }
        for stat_name, stat_value in stats.items():
            data: bytes = int_to_bytes_str(stat_value) if isinstance(stat_value, int) else stat_value.encode("utf-8")
            tasks.append(self.schedule_broadcast_sys_topic(stat_name, data))

        # Wait until broadcasting tasks end
        while tasks and tasks[0].done():
            tasks.popleft()

        # Reschedule
        sys_interval: int = 0
        x = self.context.config.get("sys_interval") if self.context.config is not None else None
        if isinstance(x, str | Buffer | SupportsInt | SupportsIndex):
            sys_interval = int(x)
        self.context.logger.debug("Broadcasting $SYS topics")

        self.context.logger.debug(f"Setup $SYS broadcasting every {sys_interval} seconds")
        self._sys_handle = (
            self.context.loop.call_later(sys_interval, self.broadcast_dollar_sys_topics)
            if self.context.loop is not None
            else None
        )

    async def on_mqtt_packet_received(self, *, packet: PACKET, session: Session | None = None) -> None:
        """Handle incoming MQTT packets."""
        if packet:
            packet_size = packet.bytes_length
            self._stats[STAT_BYTES_RECEIVED] += packet_size
            self._stats[STAT_MSG_RECEIVED] += 1
            if packet.fixed_header.packet_type == PUBLISH:
                self._stats[STAT_PUBLISH_RECEIVED] += 1

    async def on_mqtt_packet_sent(self, *, packet: PACKET, session: Session | None = None) -> None:
        """Handle sent MQTT packets."""
        if packet:
            packet_size = packet.bytes_length
            self._stats[STAT_BYTES_SENT] += packet_size
            self._stats[STAT_MSG_SENT] += 1
            if packet.fixed_header.packet_type == PUBLISH:
                self._stats[STAT_PUBLISH_SENT] += 1

    async def on_broker_client_connected(self, client_id: str) -> None:
        """Handle broker client connection."""
        self._stats[STAT_CLIENTS_CONNECTED] += 1
        self._stats[STAT_CLIENTS_MAXIMUM] = max(
            self._stats[STAT_CLIENTS_MAXIMUM],
            self._stats[STAT_CLIENTS_CONNECTED],
        )

    async def on_broker_client_disconnected(self, client_id: str) -> None:
        """Handle broker client disconnection."""
        self._stats[STAT_CLIENTS_CONNECTED] -= 1
        self._stats[STAT_CLIENTS_DISCONNECTED] += 1
