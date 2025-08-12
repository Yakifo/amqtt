from collections import defaultdict
from dataclasses import dataclass, field
import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from amqtt.broker import BrokerContext
from amqtt.contexts import Action
from amqtt.contrib.shadows.messages import (
    GetAcceptedMessage,
    GetRejectedMessage,
    UpdateAcceptedMessage,
    UpdateDeltaMessage,
    UpdateDocumentMessage,
    UpdateIotaMessage,
)
from amqtt.contrib.shadows.models import Shadow, sync_shadow_base
from amqtt.contrib.shadows.states import (
    ShadowOperation,
    StateDocument,
    calculate_delta_update,
    calculate_iota_update,
)
from amqtt.plugins.base import BasePlugin, BaseTopicPlugin
from amqtt.session import ApplicationMessage, Session

shadow_topic_re = re.compile(r"^\$shadow/(?P<client_id>[a-zA-Z0-9_-]+?)/(?P<shadow_name>[a-zA-Z0-9_-]+?)/(?P<request>get|update)")

DeviceID = str
ShadowName = str


@dataclass
class ShadowTopic:
    device_id: DeviceID
    name: ShadowName
    message_op: ShadowOperation


def shadow_dict() -> dict[DeviceID, dict[ShadowName, StateDocument]]:
    """Nested defaultdict for shadow cache."""
    return defaultdict(shadow_dict)  # type: ignore[arg-type]


class ShadowPlugin(BasePlugin[BrokerContext]):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self._shadows: dict[DeviceID, dict[ShadowName, StateDocument]] = defaultdict(dict)

        self._engine = create_async_engine(self.config.connection)
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def on_broker_pre_start(self) -> None:
        """Sync the schema."""
        async with self._engine.begin() as conn:
            await sync_shadow_base(conn)

    @staticmethod
    def shadow_topic_match(topic: str) -> ShadowTopic | None:
        """Check if topic matches the shadow topic format."""
        # pattern is "$shadow/<username>/<shadow_name>/get, update, etc
        match = shadow_topic_re.search(topic)
        if match:
            groups = match.groupdict()
            return ShadowTopic(groups["client_id"], groups["shadow_name"], ShadowOperation(groups["request"]))
        return None

    async def _handle_get(self, st: ShadowTopic) -> None:
        """Send 'accepted."""
        async with self._db_session_maker() as db_session, db_session.begin():
            shadow = await Shadow.latest_version(db_session, st.device_id, st.name)
            if not shadow:
                reject_msg = GetRejectedMessage(
                    code=404,
                    message="shadow not found",
                )
                await self.context.broadcast_message(reject_msg.topic(st.device_id, st.name), reject_msg.to_message())
                return

            accept_msg = GetAcceptedMessage(
                state=shadow.state.state,
                metadata=shadow.state.metadata,
                timestamp=shadow.created_at,
                version=shadow.version
            )
            await self.context.broadcast_message(accept_msg.topic(st.device_id, st.name), accept_msg.to_message())

    async def _handle_update(self, st: ShadowTopic, update: dict[str, Any]) -> None:
        async with self._db_session_maker() as db_session, db_session.begin():
            shadow = await Shadow.latest_version(db_session, st.device_id, st.name)
            if not shadow:
                shadow = Shadow(device_id=st.device_id, name=st.name)

            state_update = StateDocument.from_dict(update)

            prev_state = shadow.state or StateDocument()
            prev_state.version = shadow.version or 0  # only required when generating shadow messages
            prev_state.timestamp = shadow.created_at or 0  # only required when generating shadow messages

            next_state = prev_state + state_update

            shadow.state = next_state
            db_session.add(shadow)
            await db_session.commit()

            next_state.version = shadow.version
            next_state.timestamp = shadow.created_at

            accept_msg = UpdateAcceptedMessage(
                state=next_state.state,
                metadata=next_state.metadata,
                timestamp=123,
                version=1
            )

            await self.context.broadcast_message(accept_msg.topic(st.device_id, st.name), accept_msg.to_message())

            delta_msg = UpdateDeltaMessage(
                state=calculate_delta_update(next_state.state.desired, next_state.state.reported),
                metadata=calculate_delta_update(next_state.metadata.desired, next_state.metadata.reported),
                version=shadow.version,
                timestamp=shadow.created_at
            )
            await self.context.broadcast_message(delta_msg.topic(st.device_id, st.name), delta_msg.to_message())

            iota_msg = UpdateIotaMessage(
                state=calculate_iota_update(next_state.state.desired, next_state.state.reported),
                metadata=calculate_delta_update(next_state.metadata.desired, next_state.metadata.reported),
                version=shadow.version,
                timestamp=shadow.created_at
            )
            await self.context.broadcast_message(iota_msg.topic(st.device_id, st.name), iota_msg.to_message())

            doc_msg = UpdateDocumentMessage(
                previous=prev_state,
                current=next_state,
                timestamp=shadow.created_at
            )

            await self.context.broadcast_message(doc_msg.topic(st.device_id, st.name), doc_msg.to_message())

    async def on_broker_message_received(self, *, client_id: str, message: ApplicationMessage) -> None:
        """Process a message that was received from a client."""
        topic = message.topic
        if not topic.startswith("$shadow"):  # this is less overhead than do the full regular expression match
            return

        if not (shadow_topic := self.shadow_topic_match(topic)):
            return

        match shadow_topic.message_op:

            case ShadowOperation.GET:
                await self._handle_get(shadow_topic)
            case ShadowOperation.UPDATE:
                await self._handle_update(shadow_topic, json.loads(message.data.decode("utf-8")))

    @dataclass
    class Config:
        """Configuration for shadow plugin."""

        connection: str
        """SQLAlchemy connection string for the asyncio version of the database connector:

        - `mysql+aiomysql://user:password@host:port/dbname`
        - `postgresql+asyncpg://user:password@host:port/dbname`
        - `sqlite+aiosqlite:///dbfilename.db`
        """


class ShadowTopicAuthPlugin(BaseTopicPlugin):

    async def topic_filtering(self, *,
                        session: Session | None = None,
                        topic: str | None = None,
                        action: Action | None = None) -> bool | None:

        session = session or Session()
        if not topic:
            return False

        shadow_topic = ShadowPlugin.shadow_topic_match(topic)

        if not shadow_topic:
            return False

        return shadow_topic.device_id == session.username or session.username in self.config.superusers

    @dataclass
    class Config:
        """Configuration for only allowing devices access to their own shadow topics."""

        superusers: list[str] = field(default_factory=list)
        """A list of one or more usernames that can write to any device topic,
         primarily for the central app sending updates to devices."""
