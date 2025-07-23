from dataclasses import dataclass, field
import logging

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


from amqtt.broker import BrokerContext
from amqtt.contexts import Action

from amqtt.contrib.auth_db.models import PasswordHasher, Base, AllowedTopic
from amqtt.contrib.auth_db.managers import TopicManager, UserManager
from amqtt.errors import MQTTError
from amqtt.plugins.base import BaseAuthPlugin, BaseTopicPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


def default_hash_scheme() -> list[str]:
    """Create config dataclass defaults."""
    return ["argon2", "bcrypt", "pbkdf2_sha256", "scrypt"]


class AuthDBPlugin(BaseAuthPlugin, BaseTopicPlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        # access the singleton and set the proper crypt context
        pwd_hasher = PasswordHasher()
        pwd_hasher.crypt_context = CryptContext(schemes=self.config.hash_schemes, deprecated="auto")

        self._user_manager = UserManager(self.config.connection)
        self._topic_manager = TopicManager(self.config.connection)

        self._engine = create_async_engine(f"{self.config.connection}")
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def on_broker_pre_start(self) -> None:
        """Sync the schema (if configured)."""
        if not self.config.sync_schema:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def authenticate(self, *, session: Session) -> bool | None:
        """Authenticate a client's session."""
        if not session.username:
            return False

        user_auth = await self._user_manager.get_user(session.username)
        if not user_auth:
            return False

        return session.password and user_auth.verify_password(session.password)


    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool:
        if self.config.disable_topic_filtering:
            return True
        try:
            topic_list = await self._topic_manager.get_topic_list(session.username, action)
        except MQTTError:
            return False

        return AllowedTopic(topic) in topic_list

    @dataclass
    class Config:
        """Configuration for DB authentication."""

        connection: str
        """SQLAlchemy connection string for the asyncio version of the database connector:
        - mysql+aiomysql://user:password@host:port/dbname
        - postgresql+asyncpg://user:password@host:port/dbname
        - sqlite+aiosqlite:///dbfilename.db
        """
        sync_schema: bool = False
        """Use SQLAlchemy to create / update the database schema."""
        hash_schemes: list[str] = field(default_factory=default_hash_scheme)
        """An ordered list of which algorithms to hash and verify passwords."""
        disable_topic_filtering: bool = False
