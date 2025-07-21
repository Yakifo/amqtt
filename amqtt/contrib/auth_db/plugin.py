from dataclasses import dataclass, field
import logging
from typing import Any, Optional

from passlib.context import CryptContext
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from amqtt.broker import BrokerContext
from amqtt.plugins.base import BaseAuthPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


class PasswordHasher:
    """singleton to initialize the CryptContext and then use it elsewhere in the code."""

    _instance: Optional["PasswordHasher"] = None

    def __init__(self) -> None:
        if not hasattr(self, "_crypt_context"):
            self._crypt_context: CryptContext | None = None

    def __new__(cls, *args: list[Any], **kwargs: dict[str, Any]) -> "PasswordHasher":
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    @property
    def crypt_context(self) -> "CryptContext":
        if not self._crypt_context:
            msg = "CryptContext is empty"
            raise ValueError(msg)
        return self._crypt_context

    @crypt_context.setter
    def crypt_context(self, value: "CryptContext") -> None:
        self._crypt_context = value


class UserAuth(Base):
    __tablename__ = "user_auth"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    _password_hash: Mapped[str] = mapped_column("password_hash", String(128))

    @hybrid_property
    def password(self) -> None:
        msg = "Password is write-only"
        raise AttributeError(msg)

    @password.inplace.setter  # type: ignore[arg-type]
    def _password_setter(self, plain_password: str) -> None:
        self._password_hash = PasswordHasher().crypt_context.hash(plain_password)

    def verify_password(self, plain_password: str) -> bool:
        return bool(PasswordHasher().crypt_context.verify(plain_password, self._password_hash))

    def __str__(self) -> str:
        """Display client id and password hash."""
        return f"Client: '{self.username}': password hash: {self._password_hash}"



def default_hash_scheme() -> list[str]:
    """Create config dataclass defaults."""
    return ["argon2", "bcrypt", "pbkdf2_sha256", "scrypt"]


class AuthDBPlugin(BaseAuthPlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        # access the singleton and set the proper crypt context
        pwd_hasher = PasswordHasher()
        pwd_hasher.crypt_context = CryptContext(schemes=self.config.hash_schemes, deprecated="auto")

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

        async with self._db_session_maker() as db_session, db_session.begin():

            stmt = select(UserAuth).filter(UserAuth.username == session.username)
            user_auth = await db_session.scalar(stmt)
            if not user_auth:
                logger.info(f"Username '{session.username}' does not exist.")
                return False

            await db_session.flush()
            if session.password and user_auth.verify_password(session.password):
                return True
            logger.info(f"Username '{session.username}' password mismatch.")
            return False


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
