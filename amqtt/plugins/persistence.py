from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, TypeVar
import warnings

from sqlalchemy import JSON, Boolean, Integer, LargeBinary, String
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from amqtt.broker import BrokerContext
from amqtt.errors import PluginError
from amqtt.mqtt.constants import QOS_0
from amqtt.plugins.base import BasePlugin


class SQLitePlugin:

    def __init__(self) -> None:
        warnings.warn("SQLitePlugin is deprecated, use amqtt.plugins.persistence.SessionDBPlugin", stacklevel=1)

class Base(DeclarativeBase):
    pass


class RetainedMessage:
    topic: str
    data: str
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

class Session(Base):
    __tablename__ = "sessions"

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

class SessionDBPlugin(BasePlugin[BrokerContext]):
    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self._engine = create_async_engine(f"sqlite+aiosqlite:///{self.config.file}")


    async def on_broker_client_connected(self, client_id:str) -> None:
        """Search to see if session already exists."""
        # if client id doesn't exist, create (can ignore if session is anonymous)
        # update session information (will, clean_session, etc)

    async def on_broker_client_subscribed(self, client_id: str, topic: str, qos: int) -> None:
        """Store subscription if clean session = false."""

    async def on_broker_client_unsubscribed(self, client_id: str, topic: str) -> None:
        """Remove subscription if clean session = false."""

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

        await self.context.add_subscription("test_client1", "a/b", QOS_0)

    async def on_broker_pre_shutdown(self) -> None:
        """Clean up the db connection."""
        await self._engine.dispose()

    @dataclass
    class Config:
        """Configuration variables."""

        file: str = "amqtt.sqlite3"
