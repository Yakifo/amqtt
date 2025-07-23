from collections.abc import Iterator
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from amqtt.contexts import Action
from amqtt.contrib.auth_db.models import AllowedTopic, Base, TopicAuth, UserAuth
from amqtt.errors import MQTTError

logger = logging.getLogger(__name__)


class UserManager:

    def __init__(self, connection: str) -> None:
        self._engine = create_async_engine(connection)
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def db_sync(self) -> None:
        """Sync the database schema."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    async def _get_auth_or_raise(db_session: AsyncSession, username: str) -> UserAuth:
        stmt = select(UserAuth).filter(UserAuth.username == username)
        user_auth = await db_session.scalar(stmt)
        if not user_auth:
            msg = f"Username '{username}' doesn't exist."
            logger.debug(msg)
            raise MQTTError(msg)

        return user_auth

    async def get_user_auth(self, username: str) -> UserAuth | None:
        """Retrieve a user by username."""
        async with self._db_session_maker() as db_session, db_session.begin():
            try:
                return await self._get_auth_or_raise(db_session, username)
            except MQTTError:
                return None

    async def list_user_auths(self) -> Iterator[UserAuth]:
        """Return list of all clients."""
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(UserAuth).order_by(UserAuth.username)
            users = await db_session.scalars(stmt)
            if not users:
                msg = "No users exist."
                logger.info(msg)
                raise MQTTError(msg)
            return users

    async def create_user_auth(self, username: str, plain_password:str) -> UserAuth | None:
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

    async def delete_user_auth(self, username: str) -> UserAuth | None:
        """Delete a user."""
        async with self._db_session_maker() as db_session, db_session.begin():

            try:
                user_auth = await self._get_auth_or_raise(db_session, username)
            except MQTTError:
                return None

            await db_session.delete(user_auth)
            await db_session.commit()
            await db_session.flush()
            return user_auth

    async def update_user_auth_password(self, username: str, plain_password: str) -> UserAuth | None:
        """Change a user's password."""
        async with self._db_session_maker() as db_session, db_session.begin():
            user_auth = await self._get_auth_or_raise(db_session, username)
            user_auth.password = plain_password
            await db_session.commit()
            await db_session.flush()
            return user_auth


class TopicManager:

    def __init__(self, connection: str) -> None:
        self._engine = create_async_engine(connection)
        self._db_session_maker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def db_sync(self) -> None:
        """Sync the database schema."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    async def _get_auth_or_raise(db_session: AsyncSession, username: str) -> TopicAuth:
        stmt = select(TopicAuth).filter(TopicAuth.username == username)
        topic_auth = await db_session.scalar(stmt)
        if not topic_auth:
            msg = f"Username '{username}' doesn't exist."
            logger.debug(msg)
            raise MQTTError(msg)

        return topic_auth

    @staticmethod
    def _field_name(action: Action) -> str:
        return f"{action}_acl"

    async def create_topic_auth(self, username: str) -> TopicAuth | None:
        """Create a new user."""
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(TopicAuth).filter(TopicAuth.username == username)
            topic_auth = await db_session.scalar(stmt)
            if topic_auth:
                msg = f"Username '{username}' already exists."
                raise MQTTError(msg)

            topic_auth = TopicAuth(username=username)

            db_session.add(topic_auth)
            await db_session.commit()
            await db_session.flush()
            return topic_auth

    async def get_topic_auth(self, username: str) -> TopicAuth | None:
        """Retrieve a allowed topics by username."""
        async with self._db_session_maker() as db_session, db_session.begin():
            try:
                return await self._get_auth_or_raise(db_session, username)
            except MQTTError:
                return None

    async def list_topic_auths(self) -> Iterator[TopicAuth]:
        """Return list of all authorized clients."""
        async with self._db_session_maker() as db_session, db_session.begin():
            stmt = select(TopicAuth).order_by(TopicAuth.username)
            topics = await db_session.scalars(stmt)
            if not topics:
                msg = "No topics exist."
                logger.info(msg)
                raise MQTTError(msg)
            return topics

    async def add_allowed_topic(self, username: str, topic: str, action: Action) -> list[AllowedTopic] | None:
        """Add allowed topic from action for user."""
        if action == Action.PUBLISH and topic.startswith("$"):
            msg = "MQTT does not allow clients to publish to $ topics."
            raise MQTTError(msg)

        async with self._db_session_maker() as db_session, db_session.begin():
            user_auth = await self._get_auth_or_raise(db_session, username)
            topic_list = getattr(user_auth, self._field_name(action))

            updated_list = [*topic_list, AllowedTopic(topic)]
            setattr(user_auth, self._field_name(action), updated_list)
            await db_session.commit()
            await db_session.flush()
            return updated_list

    async def remove_allowed_topic(self, username: str, topic: str, action: Action) -> list[AllowedTopic] | None:
        """Remove topic from action for user."""
        async with self._db_session_maker() as db_session, db_session.begin():
            topic_auth = await self._get_auth_or_raise(db_session, username)
            topic_list = topic_auth.get_topic_list(action)

            if AllowedTopic(topic) not in topic_list:
                msg = f"Client '{username}' doesn't have topic '{topic}' for action '{action}'."
                logger.debug(msg)
                raise MQTTError(msg)

            updated_list = [allowed_topic for allowed_topic in topic_list if allowed_topic != AllowedTopic(topic)]

            setattr(topic_auth, f"{action}_acl", updated_list)
            await db_session.commit()
            await db_session.flush()
            return updated_list
