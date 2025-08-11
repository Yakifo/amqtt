from dataclasses import dataclass, field
import logging

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine

from amqtt.broker import BrokerContext
from amqtt.contexts import Action
from amqtt.contrib.auth_db.managers import TopicManager, UserManager
from amqtt.contrib.auth_db.models import Base, PasswordHasher
from amqtt.errors import MQTTError
from amqtt.plugins.base import BaseAuthPlugin, BaseTopicPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


def default_hash_scheme() -> list[str]:
    """Create config dataclass defaults."""
    return ["argon2", "bcrypt", "pbkdf2_sha256", "scrypt"]


class UserAuthDBPlugin(BaseAuthPlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        # access the singleton and set the proper crypt context
        pwd_hasher = PasswordHasher()
        pwd_hasher.crypt_context = CryptContext(schemes=self.config.hash_schemes, deprecated="auto")

        self._user_manager = UserManager(self.config.connection)
        self._engine = create_async_engine(f"{self.config.connection}")

    async def on_broker_pre_start(self) -> None:
        """Sync the schema (if configured)."""
        if not self.config.sync_schema:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def authenticate(self, *, session: Session) -> bool | None:
        """Authenticate a client's session."""
        if not session.username or not session.password:
            return False

        user_auth = await self._user_manager.get_user_auth(session.username)
        if not user_auth:
            return False

        return bool(session.password) and user_auth.verify_password(session.password)

    @dataclass
    class Config:
        """Configuration for DB authentication."""

        connection: str
        """SQLAlchemy connection string for the asyncio version of the database connector:

        - `mysql+aiomysql://user:password@host:port/dbname`
        - `postgresql+asyncpg://user:password@host:port/dbname`
        - `sqlite+aiosqlite:///dbfilename.db`
        """
        sync_schema: bool = False
        """Use SQLAlchemy to create / update the database schema."""
        hash_schemes: list[str] = field(default_factory=default_hash_scheme)
        """list of hash schemes to use for passwords"""


class TopicAuthDBPlugin(BaseTopicPlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        self._topic_manager = TopicManager(self.config.connection)
        self._engine = create_async_engine(f"{self.config.connection}")

    async def on_broker_pre_start(self) -> None:
        """Sync the schema (if configured)."""
        if not self.config.sync_schema:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool | None:
        if not session or not session.username or not topic:
            return None

        try:
            topic_auth = await self._topic_manager.get_topic_auth(session.username)
            topic_list = getattr(topic_auth, f"{action}_acl")
        except MQTTError:
            return False

        return topic in topic_list

    @dataclass
    class Config:
        """Configuration for DB topic filtering."""

        connection: str
        """SQLAlchemy connection string for the asyncio version of the database connector:

        - `mysql+aiomysql://user:password@host:port/dbname`
        - `postgresql+asyncpg://user:password@host:port/dbname`
        - `sqlite+aiosqlite:///dbfilename.db`
        """
        sync_schema: bool = False
        """Use SQLAlchemy to create / update the database schema."""
