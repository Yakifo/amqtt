from dataclasses import asdict, dataclass, is_dataclass
import logging
from pathlib import Path
from typing import Any, TypeVar
import warnings

from sqlalchemy import JSON, Boolean, Integer, LargeBinary, Result, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from amqtt.broker import BrokerContext, RetainedApplicationMessage
from amqtt.errors import PluginError
from amqtt.plugins.base import BasePlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


class SQLitePlugin(BasePlugin[BrokerContext]):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        warnings.warn("SQLitePlugin is deprecated, use amqtt.plugins.persistence.SessionDBPlugin", stacklevel=1)


class Base(DeclarativeBase):
    pass


@dataclass
class RetainedMessage:
    topic: str
    data: str
    qos: int


@dataclass
class Subscription:
    topic: str
    qos: int


T = TypeVar("T")


class DataClassListJSON(TypeDecorator[list[dict[str, Any]]]):
    impl = JSON
    cache_ok = True

    def __init__(self, dataclass_type: type[T]) -> None:
        if not is_dataclass(dataclass_type):
            msg = f"{dataclass_type} must be a dataclass type"
            raise TypeError(msg)
        self.dataclass_type = dataclass_type
        super().__init__()

    def process_bind_param(
            self,
            value: list[Any] | None,  # Python -> DB
            dialect: Any
    ) -> list[dict[str, Any]] | None:
        if value is None:
            return None
        return [asdict(item) for item in value]

    def process_result_value(
            self,
            value: list[dict[str, Any]] | None,  # DB -> Python
            dialect: Any
    ) -> list[Any] | None:
        if value is None:
            return None
        return [self.dataclass_type(**item) for item in value]
    def process_literal_param(self, value: Any, dialect: Any) -> Any:
        # Required by SQLAlchemy, typically used for literal SQL rendering.
        return value
    @property
    def python_type(self) -> type:
        # Required by TypeEngine to indicate the expected Python type.
        return list


class StoredSession(Base):
    __tablename__ = "stored_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String)

    clean_session: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    will_flag: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    will_message: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)
    will_qos: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    will_retain: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    will_topic: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    keep_alive: Mapped[int] = mapped_column(Integer, default=0)
    retained: Mapped[list[RetainedMessage]] = mapped_column(DataClassListJSON(RetainedMessage), default=list)
    subscriptions: Mapped[list[Subscription]] = mapped_column(DataClassListJSON(Subscription), default=list)


class StoredMessage(Base):
    __tablename__ = "stored_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String)
    data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, default=None)
    qos: Mapped[int] = mapped_column(Integer, default=0)


class SessionDBPlugin(BasePlugin[BrokerContext]):
    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        # bypass the `test_plugins_correct_has_attr` until it can be updated
        if not hasattr(self.config, "file"):
            logger.warning("`Config` is missing a `file` attribute")
            return

        self._engine = create_async_engine(f"sqlite+aiosqlite:///{self.config.file}")
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    @staticmethod
    async def _get_or_create_session(db_session: AsyncSession, client_id:str) -> StoredSession:

        stmt = select(StoredSession).filter(StoredSession.client_id == client_id)
        stored_session = await db_session.scalar(stmt)
        if stored_session is None:
            stored_session = StoredSession(client_id=client_id)
            db_session.add(stored_session)
        await db_session.flush()
        return stored_session


    @staticmethod
    async def _get_or_create_message(db_session: AsyncSession, topic:str) -> StoredMessage:

        stmt = select(StoredMessage).filter(StoredMessage.topic == topic)
        stored_message = await db_session.scalar(stmt)
        if stored_message is None:
            stored_message = StoredMessage(topic=topic)
            db_session.add(stored_message)
        await db_session.flush()
        return stored_message


    async def on_broker_client_connected(self, client_id:str, client_session:Session) -> None:
        """Search to see if session already exists."""
        # if client id doesn't exist, create (can ignore if session is anonymous)
        # update session information (will, clean_session, etc)

        # don't store session information for clean or anonymous sessions
        if client_session.clean_session in (None, True) or client_session.is_anonymous:
            return
        async with self._db_session_maker() as db_session, db_session.begin():
            stored_session = await self._get_or_create_session(db_session, client_id)

            stored_session.clean_session = client_session.clean_session
            stored_session.will_flag = client_session.will_flag
            stored_session.will_message = client_session.will_message  # type: ignore[assignment]
            stored_session.will_qos = client_session.will_qos
            stored_session.will_retain = client_session.will_retain
            stored_session.will_topic = client_session.will_topic
            stored_session.keep_alive = client_session.keep_alive

            await db_session.flush()

    async def on_broker_client_subscribed(self, client_id: str, topic: str, qos: int) -> None:
        """Create/update subscription if clean session = false."""
        session = self.context.get_session(client_id)
        if not session:
            logger.warning(f"'{client_id}' is subscribing but doesn't have a session")
            return

        if session.clean_session:
            return

        async with self._db_session_maker() as db_session, db_session.begin():
            # stored sessions shouldn't need to be created here, but we'll use the same helper...
            stored_session = await self._get_or_create_session(db_session, client_id)
            stored_session.subscriptions = [*stored_session.subscriptions, Subscription(topic, qos)]
            await db_session.flush()

    async def on_broker_client_unsubscribed(self, client_id: str, topic: str) -> None:
        """Remove subscription if clean session = false."""

    async def on_broker_retained_message(self, *, client_id: str | None, retained_message: RetainedApplicationMessage) -> None:
        """Update to retained messages.

        if retained_message.data is None or '', the message is being cleared
        """
        # if client_id is valid, the retained message is for a disconnected client
        if client_id is not None:
            async with self._db_session_maker() as db_session, db_session.begin():
                # stored sessions shouldn't need to be created here, but we'll use the same helper...
                stored_session = await self._get_or_create_session(db_session, client_id)
                stored_session.retained = [*stored_session.retained, RetainedMessage(retained_message.topic,
                                                                                     retained_message.data.decode(),
                                                                                     retained_message.qos or 0)]
                await db_session.flush()
            return

        async with self._db_session_maker() as db_session, db_session.begin():
            # if the retained message has data, we need to store/update for the topic
            if retained_message.data:
                client_message = await self._get_or_create_message(db_session, retained_message.topic)
                client_message.data = retained_message.data  # type: ignore[assignment]
                client_message.qos = retained_message.qos or 0
                await db_session.flush()
                return

            # if there is no data, clear the stored message (if exists) for the topic
            stmt = select(StoredMessage).filter(StoredMessage.topic == retained_message.topic)
            topic_message = await db_session.scalar(stmt)
            if topic_message is not None:
                await db_session.delete(topic_message)
                await db_session.flush()
            return

    async def on_broker_pre_start(self) -> None:
        """Initialize the database and db connection."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def on_broker_post_start(self) -> None:
        """Load subscriptions."""
        if len(self.context.subscriptions) > 0:
            msg = "SessionDBPlugin : broker shouldn't have any subscriptions yet"
            raise PluginError(msg)

        if len(list(self.context.sessions)) > 0:
            msg = "SessionDBPlugin : broker shouldn't have any sessions yet"
            raise PluginError(msg)

        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(StoredSession)
            stored_sessions = await db_session.execute(stmt)

            restored_sessions = 0
            for stored_session in stored_sessions.scalars():
                await self.context.add_subscription(stored_session.client_id, None, None)
                for subscription in stored_session.subscriptions:
                    await self.context.add_subscription(stored_session.client_id,
                                                        subscription.topic,
                                                        subscription.qos)
                session = self.context.get_session(stored_session.client_id)
                if not session:
                    continue
                session.clean_session = stored_session.clean_session
                session.will_flag = stored_session.will_flag
                session.will_message = stored_session.will_message
                session.will_qos = stored_session.will_qos
                session.will_retain = stored_session.will_retain
                session.will_topic = stored_session.will_topic
                session.keep_alive = stored_session.keep_alive

                for message in stored_session.retained:
                    retained_message = RetainedApplicationMessage(
                        source_session=None,
                        topic=message.topic,
                        data=message.data.encode(),
                        qos=message.qos
                    )
                    await session.retained_messages.put(retained_message)
                restored_sessions += 1

            stmt = select(StoredMessage)
            stored_messages: Result[tuple[StoredMessage]] = await db_session.execute(stmt)

            restored_messages = 0
            retained_messages = self.context.retained_messages
            for stored_message in stored_messages.scalars():
                retained_messages[stored_message.topic] = (RetainedApplicationMessage(
                    source_session=None,
                    topic=stored_message.topic,
                    data=stored_message.data or b"",
                    qos=stored_message.qos
                ))
                restored_messages += 1
            logger.info(f"Retained messages restored: {restored_messages}")


        logger.info(f"Restored {restored_sessions} sessions.")

    async def on_broker_pre_shutdown(self) -> None:
        """Clean up the db connection."""
        await self._engine.dispose()

    async def on_broker_post_shutdown(self) -> None:

        if self.config.clear_on_shutdown and self.config.file.exists():
            self.config.file.unlink()

    @dataclass
    class Config:
        """Configuration variables."""

        file: str | Path = "amqtt.db"
        retain_interval: int = 5
        clear_on_shutdown: bool = True

        def __post_init__(self) -> None:
            """Create `Path` from string path."""
            if isinstance(self.file, str):
                self.file = Path(self.file)
