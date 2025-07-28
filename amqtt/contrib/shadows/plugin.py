from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from sqlalchemy.ext.asyncio import create_async_engine

from amqtt.broker import BrokerContext
from amqtt.contrib.auth_db.models import Base
from amqtt.contrib.shadows.states import StateDocument
from amqtt.plugins.base import BasePlugin
from amqtt.session import ApplicationMessage

shadow_topic_re = re.compile(r"^\$shadow/(?P<client_id>[a-zA-Z0-9_-]+?)/(?P<shadow_name>[a-zA-Z0-9_-]+?)/(?P<request>get|update)")

class ShadowOperation(StrEnum):
    GET = "get"
    UPDATE = "update"
    ACCEPT = "accept"
    REJECT = "reject"
    DOCUMENT = "document"
    DELETE = "delta"
    IOTA = "iota"


@dataclass
class ShadowTopic:
    client_id: str
    name: str
    message_type: ShadowOperation


ClientID= str
ShadowName = str

class ShadowPlugin(BasePlugin[BrokerContext]):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self._shadows: dict[ClientID, dict[ShadowName, StateDocument]] = {}

        self._engine = create_async_engine(f"{self.config.connection}")

    async def on_broker_pre_start(self) -> None:
        """Sync the schemad."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    def shadow_topic_match(topic: str) -> ShadowTopic | None:
        """Check if topic matches the shadow topic format."""
        # pattern is "$shadow/<username>/<shadow_name>/get, update, etc
        match = shadow_topic_re.search(topic)
        if match:
            groups = match.groupdict()
            return ShadowTopic(groups["client_id"], groups["shadow_name"], ShadowOperation(groups["request"]))
        return None

    async def _handle_get(self, device_id: str, name: str) -> None:
        """Send 'accepted."""
        await self.context.broadcast_message("topic", b"message")

    async def _handle_update(self, device_id: str, name: str, state: dict[str, Any]) -> None:

        await self.context.broadcast_message("topic", b"message")

    async def on_broker_message_received(self, *, client_id: str, message: ApplicationMessage) -> None:
        """Process a message that was received from a client."""
        topic = message.topic
        if not topic.startswith("$shadow"):  # this is less overhead than do the full regular expression match
            return

        if not (shadow_topic := self.shadow_topic_match(topic)):
            return

        if shadow_topic.client_id not in self._shadows:
            self._shadows[shadow_topic.client_id] = {}

        if shadow_topic.name not in self._shadows[shadow_topic.client_id]:
            self._shadows[shadow_topic.client_id][shadow_topic.name] = StateDocument()

        match shadow_topic.message_type:

            case ShadowOperation.GET:
                await self._handle_get(shadow_topic.client_id, shadow_topic.name)
            case ShadowOperation.UPDATE:
                await self._handle_update(shadow_topic.client_id, "shadow name", {})
