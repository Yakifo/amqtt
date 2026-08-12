from collections.abc import Sequence
from dataclasses import dataclass
import logging
from typing import ClassVar, Union, cast
from typing_extensions import Self
import warnings

from pwdlib import PasswordHash
from pwdlib.hashers import HasherProtocol
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from amqtt.contexts import Action
from amqtt.contrib import DataClassListJSON
from amqtt.contrib.auth_db.hasher import LegacyPasslibPBKDF2Hasher, LegacyPasslibScryptHasher
from amqtt.plugins import TopicMatcher

logger = logging.getLogger(__name__)

matcher = TopicMatcher()


@dataclass
class AllowedTopic:
    topic: str

    def __contains__(self, item: Union[str, "AllowedTopic"]) -> bool:
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


class PasswordHasher(PasswordHash):
    """Singleton password hashing context shared across auth DB models."""

    _instance: ClassVar[Self | None] = None

    def __new__(
        cls,
        hashers: Sequence[HasherProtocol] | None = None,
        schemes: Sequence[str] | None = None,
    ) -> Self:
        del hashers, schemes
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        hashers: Sequence[HasherProtocol] | None = None,
        schemes: Sequence[str] | None = None,
    ) -> None:
        if hasattr(self, "hashers"):
            return

        if hashers is not None and schemes is not None:
            msg = "'hashers' and 'schemes' cannot both be specified."
            raise ValueError(msg)

        super().__init__(tuple(hashers) if hashers is not None else self._make_hashers(schemes))

    @property
    def crypt_context(self) -> "PasswordHasher":
        """Preserve the previous ``PasswordHasher().crypt_context`` API."""
        return self

    def verify(self, password: str | bytes, hash: str | bytes) -> bool:  # ruff: ignore[builtin-argument-shadowing]# pylint: disable=redefined-builtin
        password, password_hash = self._normalize_verify_args(password, hash)
        return super().verify(password, password_hash)

    def verify_and_update(self, password: str | bytes, hash: str | bytes) -> tuple[bool, str | None]:  # ruff: ignore[builtin-argument-shadowing]# pylint: disable=redefined-builtin
        password, password_hash = self._normalize_verify_args(password, hash)
        return super().verify_and_update(password, password_hash)

    def _normalize_verify_args(
        self,
        password: str | bytes,
        password_hash: str | bytes,
    ) -> tuple[str | bytes, str | bytes]:
        if self._is_password_hash(password) and not self._is_password_hash(password_hash):
            return password_hash, password
        return password, password_hash

    def _is_password_hash(self, value: str | bytes) -> bool:
        for hasher in self.hashers:
            try:
                if hasher.identify(value):
                    return True
            except AttributeError:
                continue
        return False

    @staticmethod
    def _make_hashers(schemes: Sequence[str] | None = None) -> tuple[HasherProtocol, ...]:
        if not schemes:
            schemes = ("argon2", "bcrypt")

        if "pbkdf2_sha256" in schemes or "scrypt" in schemes:
            warnings.warn(
                "'pbkdf2_sha256' and 'scrypt' are deprecated. Existing passwords will be verified and upgraded "
                "to Argon2 on the next password change.",
                DeprecationWarning,
                stacklevel=2,
            )
            if "argon2" not in schemes:
                schemes = ("argon2", *schemes)

        hash_scheme_map: dict[str, type[HasherProtocol]] = {
            "argon2": Argon2Hasher,
            "bcrypt": BcryptHasher,
            "pbkdf2_sha256": cast("type[HasherProtocol]", LegacyPasslibPBKDF2Hasher),
            "scrypt": cast("type[HasherProtocol]", LegacyPasslibScryptHasher),
        }

        try:
            return tuple(hash_scheme_map[scheme]() for scheme in schemes)
        except KeyError as exc:
            msg = f"Unsupported password hash scheme: {exc.args[0]}"
            raise ValueError(msg) from exc


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

    @property
    def password(self) -> None:
        msg = "Password is write-only"
        raise AttributeError(msg)

    @password.setter
    def password(self, plain_password: str) -> None:
        self._password_hash = PasswordHasher().hash(plain_password)

    def verify_password(self, plain_password: str) -> bool:
        is_valid, updated_hash = PasswordHasher().verify_and_update(plain_password, self._password_hash)
        if is_valid and updated_hash:
            self._password_hash = updated_hash
        return is_valid

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
