from collections.abc import Iterator

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from amqtt.contrib.auth_db.plugin import Base, PasswordHasher, UserAuth, default_hash_scheme, logger
from amqtt.errors import MQTTError


class UserManager:

    def __init__(self, connection: str) -> None:
        self._engine = create_async_engine(connection)
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)
        pwd_hasher = PasswordHasher()
        pwd_hasher.crypt_context = CryptContext(schemes=default_hash_scheme(), deprecated="auto")

    async def db_sync(self) -> None:
        """Sync the database schema."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def list_users(self) -> Iterator[UserAuth]:
        """Return list of all clients."""
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).order_by(UserAuth.username)
            users = await db_session.scalars(stmt)
            if not users:
                msg = "No users exist."
                logger.info(msg)
                raise MQTTError(msg)
            return users

    async def create_user(self, username: str, plain_password:str) -> UserAuth | None:
        """Create a new user."""
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).filter(UserAuth.username == username)
            user_auth = await db_session.scalar(stmt)
            if user_auth:
                msg = f"Username '{username}' already exists."
                logger.info(msg)
                raise MQTTError(msg)

            user_auth = UserAuth(username=username)
            user_auth.password = plain_password
            db_session.add(user_auth)
            await db_session.commit()
            await db_session.flush()
            return user_auth

    async def delete_user(self, username: str) -> UserAuth | None:
        """Delete a user."""
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).filter(UserAuth.username == username)
            user_auth = await db_session.scalar(stmt)
            if not user_auth:
                msg = f"'{username}' doesn't exists."
                logger.info(msg)
                raise MQTTError(msg)

            await db_session.delete(user_auth)
            await db_session.commit()
            await db_session.flush()
            return user_auth

    async def update_password(self, username: str, plain_password: str) -> UserAuth | None:
        """Change a user's password."""
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).filter(UserAuth.username == username)
            user_auth = await db_session.scalar(stmt)
            if not user_auth:
                msg = f"Username '{username}' doesn't exist."
                logger.debug(msg)
                raise MQTTError(msg)

            user_auth.password = plain_password
            await db_session.commit()
            await db_session.flush()
            return user_auth
