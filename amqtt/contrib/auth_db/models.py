from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from sqlalchemy import String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from amqtt.contexts import Action
from amqtt.contrib import DataClassListJSON
from amqtt.plugins import TopicMatcher

if TYPE_CHECKING:
    from passlib.context import CryptContext


logger = logging.getLogger(__name__)

matcher = TopicMatcher()

@dataclass
class AllowedTopic:
    topic: str

    def __contains__(self, item: Union[str,"AllowedTopic"]) -> bool:
        """Determine `in`."""
        return self.__eq__(item)

    def __eq__(self, item: object) -> bool:
        """Determine `==` or `!=`."""
        if isinstance(item, str):
            return matcher.is_topic_allowed(item, self.topic)
        if isinstance(item, AllowedTopic):
            return item.topic == self.topic
        msg = "AllowedTopic can only be compared to another AllowedTopic or string."
        raise AttributeError(msg)

    def __str__(self) -> str:
        """Display topic."""
        return self.topic

    def __repr__(self) -> str:
        """Display topic."""
        return self.topic

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


class Base(DeclarativeBase):
    pass


class UserAuth(Base):
    __tablename__ = "user_auth"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    _password_hash: Mapped[str] = mapped_column("password_hash", String(128))

    publish_acl: Mapped[list[AllowedTopic]] = mapped_column(DataClassListJSON(AllowedTopic), default=list)
    subscribe_acl: Mapped[list[AllowedTopic]] = mapped_column(DataClassListJSON(AllowedTopic), default=list)
    receive_acl: Mapped[list[AllowedTopic]] = mapped_column(DataClassListJSON(AllowedTopic), default=list)

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
        return f"'{self.username}' with password hash: {self._password_hash}"


class TopicAuth(Base):
    __tablename__ = "topic_auth"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)

    publish_acl: Mapped[list[AllowedTopic]] = mapped_column(DataClassListJSON(AllowedTopic), default=list)
    subscribe_acl: Mapped[list[AllowedTopic]] = mapped_column(DataClassListJSON(AllowedTopic), default=list)
    receive_acl: Mapped[list[AllowedTopic]] = mapped_column(DataClassListJSON(AllowedTopic), default=list)

    def get_topic_list(self, action: Action) -> list[AllowedTopic]:
        return cast("list[AllowedTopic]", getattr(self, f"{action}_acl"))

    def __str__(self) -> str:
        """Display client id and password hash."""
        return f"""'{self.username}':
\tpublish: {self.publish_acl}, subscribe: {self.subscribe_acl}, receive: {self.receive_acl}
"""
