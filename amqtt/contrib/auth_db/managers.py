import logging
from collections.abc import Iterator


from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from amqtt.contexts import Action
from amqtt.contrib.auth_db.models import UserAuth, Base, AllowedTopic
from amqtt.errors import MQTTError

logger = logging.getLogger(__name__)


class Manager:
    @staticmethod
    async def _get_user_or_raise(db_session: AsyncSession, username: str) -> UserAuth:
        stmt = select(UserAuth).filter(UserAuth.username == username)
        user_auth = await db_session.scalar(stmt)
        if not user_auth:
            msg = f"Username '{username}' doesn't exist."
            logger.debug(msg)
            raise MQTTError(msg)

        return user_auth


class UserManager(Manager):

    def __init__(self, connection: str) -> None:
        self._engine = create_async_engine(connection)
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def db_sync(self) -> None:
        """Sync the database schema."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_user(self, username: str) -> UserAuth | None:
        """Retrieve a user by username."""

        async with self._db_session_maker() as db_session, db_session.begin():
            try:
                return await self._get_user_or_raise(db_session, username)
            except MQTTError:
                return None

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

            user_auth = await self._get_user_or_raise(db_session, username)

            await db_session.delete(user_auth)
            await db_session.commit()
            await db_session.flush()
            return user_auth

    async def update_password(self, username: str, plain_password: str) -> UserAuth | None:
        """Change a user's password."""

        async with self._db_session_maker() as db_session, db_session.begin():
            user_auth = await self._get_user_or_raise(db_session, username)
            user_auth.password = plain_password
            await db_session.commit()
            await db_session.flush()
            return user_auth


class TopicManager(Manager):

    def __init__(self, connection: str) -> None:
        self._engine = create_async_engine(connection)
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def db_sync(self) -> None:
        """Sync the database schema."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    def _field_name(action: Action) -> str:
        return f"{action}_acl"

    async def add_topic(self, username: str, topic: str, action: Action) -> list[AllowedTopic] | None:
        """Add allowed topic for action."""
        async with self._db_session_maker() as db_session, db_session.begin():
            user_auth = await self._get_user_or_raise(db_session, username)
            topic_list = getattr(user_auth, self._field_name(action))

            updated_list = [*topic_list, AllowedTopic(topic)]
            setattr(user_auth, self._field_name(action), updated_list)
            await db_session.commit()
            await db_session.flush()
            return updated_list

    async def remove_topic(self, username: str, topic: str, action: Action) -> list[AllowedTopic] | None:
        """Remove topic from action."""
        async with self._db_session_maker() as db_session, db_session.begin():
            user_auth = await self._get_user_or_raise(db_session, username)
            topic_list: list[AllowedTopic] = getattr(user_auth, self._field_name(action))

            if AllowedTopic(topic) not in topic_list:
                logger.debug(f"Topic list for '{action}' is {topic_list}")
                raise MQTTError(f"Topic '{topic}' not found for action '{action}'.")

            updated_list = [allowed_topic for allowed_topic in topic_list if allowed_topic != AllowedTopic(topic)]

            setattr(user_auth, f"{action}_acl", updated_list)
            await db_session.commit()
            await db_session.flush()
            return updated_list

    async def get_topic_list(self, username: str, action: Action) -> list[AllowedTopic]:

        async with self._db_session_maker() as db_session, db_session.begin():
            user_auth = await self._get_user_or_raise(db_session, username)

            return getattr(user_auth, self._field_name(action))
