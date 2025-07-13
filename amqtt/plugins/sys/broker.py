import asyncio
from collections import deque  # pylint: disable=C0412
from dataclasses import dataclass
from typing import Any, SupportsIndex, SupportsInt, TypeAlias  # pylint: disable=C0412

import psutil

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
from amqtt.codecs_amqtt import float_to_bytes_str, int_to_bytes_str
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
MEMORY_USAGE_MAXIMUM = "memory_maximum"
CPU_USAGE_MAXIMUM = "cpu_usage_maximum"
CPU_USAGE_LAST = "cpu_usage_last"


PACKET: TypeAlias = MQTTPacket[MQTTVariableHeader, MQTTPayload[MQTTVariableHeader], MQTTFixedHeader]


def val_to_bytes_str(value: Any) -> bytes:
    """Convert an int, float or string to byte string."""
    match value:
        case int():
            return int_to_bytes_str(value)
        case float():
            return float_to_bytes_str(value)
        case str():
            return value.encode("utf-8")
        case _:
            msg = f"Unsupported type {type(value)}"
            raise NotImplementedError(msg)


class BrokerSysPlugin(BasePlugin[BrokerContext]):
    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        # Broker statistics initialization
        self._stats: dict[str, int] = {}
        self._sys_handle: asyncio.Handle | None = None

        self._sys_interval: int = 0
        self._current_process = psutil.Process()


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
            MEMORY_USAGE_MAXIMUM,
            CPU_USAGE_MAXIMUM
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
            self._sys_interval = self._get_config_option("sys_interval", None)
            if isinstance(self._sys_interval, str | Buffer | SupportsInt | SupportsIndex):
                self._sys_interval = int(self._sys_interval)

            if self._sys_interval > 0:
                self.context.logger.debug(f"Setup $SYS broadcasting every {self._sys_interval} seconds")
                self._sys_handle = (
                    self.context.loop.call_later(self._sys_interval, self.broadcast_dollar_sys_topics)
                    if self.context.loop is not None
                    else None
                )
            else:
                self.context.logger.debug("$SYS disabled")
        except KeyError:
            self.context.logger.debug("could not find 'sys_interval' key: {e!r}")
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
        self._stats[STAT_CLIENTS_MAXIMUM] = client_connected

        cpu_usage = self._current_process.cpu_percent(interval=0)
        self._stats[CPU_USAGE_MAXIMUM] = max(self._stats[CPU_USAGE_MAXIMUM], cpu_usage)

        mem_info_usage = self._current_process.memory_full_info()
        mem_size = mem_info_usage.rss / (1024 ** 2)
        self._stats[MEMORY_USAGE_MAXIMUM] = max(self._stats[MEMORY_USAGE_MAXIMUM], mem_size)

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
            "heap/size": mem_size,
            "heap/maximum": self._stats[MEMORY_USAGE_MAXIMUM],
            "cpu/percent": cpu_usage,
            "cpu/maximum": self._stats[CPU_USAGE_MAXIMUM],
        }
        for stat_name, stat_value in stats.items():
            data: bytes = val_to_bytes_str(stat_value)
            tasks.append(self.schedule_broadcast_sys_topic(stat_name, data))

        # Wait until broadcasting tasks end
        while tasks and tasks[0].done():
            tasks.popleft()

        # Reschedule
        self.context.logger.debug(f"Broadcast $SYS topics again in {self._sys_interval} seconds.")
        self._sys_handle = (
            self.context.loop.call_later(self._sys_interval, self.broadcast_dollar_sys_topics)
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

    async def on_broker_client_connected(self, client_id: str, client_session: Session) -> None:
        """Handle broker client connection."""
        self._stats[STAT_CLIENTS_CONNECTED] += 1
        self._stats[STAT_CLIENTS_MAXIMUM] = max(
            self._stats[STAT_CLIENTS_MAXIMUM],
            self._stats[STAT_CLIENTS_CONNECTED],
        )

    async def on_broker_client_disconnected(self, client_id: str, client_session: Session) -> None:
        """Handle broker client disconnection."""
        self._stats[STAT_CLIENTS_CONNECTED] -= 1
        self._stats[STAT_CLIENTS_DISCONNECTED] += 1

    @dataclass
    class Config:
        """Configuration struct for plugin."""

        sys_interval: int = 20
