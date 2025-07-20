from dataclasses import dataclass, field
import logging
from typing import Generator

from passlib.context import CryptContext
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from amqtt.broker import BrokerContext
from amqtt.errors import MQTTError
from amqtt.plugins.base import BaseAuthPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


class PasswordHasher:
    """singleton to initialize the CryptContext and then use it elsewhere in the code."""

    _instance: "PasswordHasher" = None

    def __init__(self):
        if not hasattr(self, '_crypt_context'):
            self._crypt_context: CryptContext | None = None

    def __new__(cls, *args: list, **kwargs: dict) -> "PasswordHasher":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def crypt_context(self) -> "CryptContext":
        if not self._crypt_context:
            raise ValueError("CryptContext is empty")
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
    def password(self):
        raise AttributeError("Password is write-only")

    @password.setter
    def password(self, plain_password: str):
        self._password_hash = PasswordHasher().crypt_context.hash(plain_password)

    def verify_password(self, plain_password: str) -> bool:
        return PasswordHasher().crypt_context.verify(plain_password, self._password_hash)

    def __str__(self):
        return f"Client: '{self.username}': password hash: {self._password_hash}"



def default_hash_scheme():
    return ["argon2", "bcrypt", "pbkdf2_sha256", "scrypt"]


class DBAuthPlugin(BaseAuthPlugin):

    def __init__(self, context: BrokerContext):
        super().__init__(context)

        # access the singleton and set the proper crypt context
        pwd_hasher = PasswordHasher()
        pwd_hasher.crypt_context = CryptContext(schemes=self.config.hash_schemes, deprecated="auto")

        self._engine = create_async_engine(f"{self.config.connection}")
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def on_broker_pre_start(self) -> None:
        """Sync the schema (if configured)"""
        if not self.config.sync_schema:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def authenticate(self, *, session: Session) -> bool | None:

        if not session.username:
            return False

        async with self._db_session_maker() as db_session, db_session.begin():

            stmt = select(UserAuth).filter(UserAuth.username == session.username)
            user_auth = await db_session.scalar(stmt)
            if not user_auth:
                logger.info(f"Username '{session.username}' does not exist.")
                return False

            await db_session.flush()
            if not user_auth.verify_password(session.password):
                logger.info(f"Username '{session.username}' password mismatch.")
                return False
            return True


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


class UserManager:

    def __init__(self, connection: str):
        self._engine = create_async_engine(connection)
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)
        pwd_hasher = PasswordHasher()
        pwd_hasher.crypt_context = CryptContext(schemes=default_hash_scheme(), deprecated="auto")

    async def db_sync(self):
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def list_users(self):
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).order_by(UserAuth.username)
            users = await db_session.scalars(stmt)
            if not users:
                logger.info("No users exist.")
                raise MQTTError("No users exist.")
            return users

    async def create_user(self, username: str, plain_password:str) -> UserAuth | None:
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).filter(UserAuth.username == username)
            user_auth = await db_session.scalar(stmt)
            if user_auth:
                logger.info(f"Username '{username}' already exists.")
                raise MQTTError("Username already exists.")

            user_auth = UserAuth(username=username)
            user_auth.password = plain_password
            db_session.add(user_auth)
            await db_session.commit()
            await db_session.flush()
            return user_auth

        return None


    async def delete_user(self, username: str) -> UserAuth | None:
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).filter(UserAuth.username == username)
            user_auth = await db_session.scalar(stmt)
            if not user_auth:
                logger.info(f"'{username}' doesn't exists.")
                raise MQTTError(f"'{username}' doesn't exists.")

            await db_session.delete(user_auth)
            await db_session.commit()
            await db_session.flush()
            return user_auth

        return None

    async def update_password(self, username: str, plain_password: str) -> UserAuth | None:
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).filter(UserAuth.username == username)
            user_auth = await db_session.scalar(stmt)
            if not user_auth:
                logger.debug(f"Username '{username}' doesn't exist.")
                raise MQTTError(f"Username '{username}' doesn't exist.")

            user_auth.password = plain_password
            await db_session.commit()
            await db_session.flush()
            return user_auth
        return None
