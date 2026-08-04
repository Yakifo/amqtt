import binascii
from collections.abc import Callable
from dataclasses import dataclass, field
import hmac
from pathlib import Path
import sys
import warnings

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers import HasherProtocol
from pwdlib.hashers.argon2 import Argon2Hasher

from amqtt.broker import BrokerContext
from amqtt.contexts import BaseContext
from amqtt.plugins.base import BaseAuthPlugin
from amqtt.session import Session

_PARTS_EXPECTED_LENGTH = 2  # Expected number of parts in a valid line


class AnonymousAuthPlugin(BaseAuthPlugin):
    """Authentication plugin allowing anonymous access."""

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        # Default to allowing anonymous
        self._allow_anonymous = self._get_config_option("allow-anonymous", True)  # ruff: ignore[boolean-positional-value-in-call]

    async def authenticate(self, *, session: Session) -> bool:
        authenticated = await super().authenticate(session=session)
        if authenticated:

            if self._allow_anonymous:
                self.context.logger.debug("Authentication success: config allows anonymous")
                session.is_anonymous = True
                return True

            if session and session.username:
                self.context.logger.debug(f"Authentication success: session has username '{session.username}'")
                return True
            self.context.logger.debug("Authentication failure: session has no username")
        return False

    @dataclass
    class Config:
        """Configuration for AnonymousAuthPlugin."""

        allow_anonymous: bool = field(default=True)
        """Allow all anonymous authentication (even with _no_ username)."""


class PasswordFileError(Exception):
    """Exception raised when there is an error with the password file."""


# Python 3.13 no longer includes `crypt` in the standard library.
# SHA512 crypt support depends on that module, so it is unavailable on Python >= 3.13.
_native_crypt: Callable[[str, str], str | None] | None = None
if sys.version_info < (3, 13):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from crypt import crypt as crypt_func  # pylint: disable=deprecated-module
        _native_crypt = crypt_func
    except ImportError:
        pass


def _ensure_str(value: str | bytes) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


class DeprecatedSHA512CryptHasher(HasherProtocol):

    @classmethod
    def identify(cls, hash: str | bytes) -> bool:  # noqa: A002# pylint: disable=redefined-builtin
        del cls
        try:
            password_hash = _ensure_str(hash)
        except UnicodeDecodeError:
            return False
        return password_hash.startswith("$6$")

    @property
    def name(self) -> str:
        return "sha512_crypt"

    def hash(self, password: str | bytes, *, salt: bytes | None = None) -> str:
        # Heavily discourage generating new hashes using this deprecated method
        msg = (
            "Generating new sha512_crypt hashes is disabled. "
            "Please use Argon2 or Bcrypt instead."
        )
        raise NotImplementedError(msg)

    def verify(self, password: str | bytes, hash: str | bytes) -> bool:  # noqa: A002# pylint: disable=redefined-builtin
        # Gracefully handle the absolute missing dependency on Python 3.13+
        if _native_crypt is None:
            warnings.warn(
                "Cannot verify 'sha512_crypt' hash. The native 'crypt' module "
                "is not available on Python 3.13+. Access is denied.",
                RuntimeWarning,
                stacklevel=2,
            )
            return False

        try:
            pwd_hash = _ensure_str(hash)
            pwd = _ensure_str(password)

            if not self.identify(pwd_hash):
                return False

            warnings.warn(
                "Authenticating with legacy 'sha512_crypt' hash format. This is "
                "deprecated and will completely break when upgrading to Python 3.13+. ",
                DeprecationWarning,
                stacklevel=2
            )

            # Passing the full hash allows the OS to parse the inner salt and rounds configuration
            computed_hash = _native_crypt(pwd, pwd_hash)

            if not computed_hash:
                return False

            return hmac.compare_digest(computed_hash, pwd_hash)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return False

    def check_needs_rehash(self, hash: str | bytes) -> bool:  # noqa: A002# pylint: disable=redefined-builtin
        return True


class FileAuthPlugin(BaseAuthPlugin):
    """Authentication plugin based on a file-stored user database."""

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self._users: dict[str, str] = {}
        self._read_password_file()
        self.pwd_hasher = PasswordHash((Argon2Hasher(), DeprecatedSHA512CryptHasher()))

    def is_hash_supported(self, hash_str: str) -> bool:
        """Check if the hash is in the deprecated format."""
        return any(hasher.identify(hash_str) for hasher in self.pwd_hasher.hashers)

    def _read_password_file(self) -> None:
        """Read the password file and populates the user dictionary."""
        password_file = self._get_config_option("password-file", None)
        if not password_file:
            self.context.logger.warning("Configuration parameter 'password-file' not found")
            return

        try:
            file = password_file
            if isinstance(file, str):
                file = Path(file)
            with file.open(mode="r", encoding="utf-8") as file:
                self.context.logger.debug(f"Reading user database from {password_file}")
                for _line in file:
                    line = _line.strip()
                    if line and not line.startswith("#"):  # Skip empty lines and comments
                        parts = line.split(":", maxsplit=1)
                        if len(parts) == _PARTS_EXPECTED_LENGTH:
                            username, pwd_hash = parts
                            if DeprecatedSHA512CryptHasher().identify(pwd_hash):
                                warnings.warn(
                                    "`sha512` password hashes are deprecated. Please use `argon2` instead.",
                                    DeprecationWarning,
                                    stacklevel=2,
                                )
                            self._users[username] = pwd_hash
                            self.context.logger.debug(f"User '{username}' loaded")
                        else:
                            self.context.logger.warning(f"Malformed line in password file: {line}")
            self.context.logger.info(f"{len(self._users)} user(s) loaded from {password_file}")
        except FileNotFoundError as e:
            msg = f"Password file '{password_file}' not found"
            raise PasswordFileError(msg) from e
        except UnknownHashError as e:
            msg = (
                f"Unsupported hash format in password file '{password_file}'. "
                "Only Argon2 or BCrypt is supported. See plugin docs for more information."
            )
            raise PasswordFileError(msg) from e
        except ValueError as e:
            msg = f"Malformed password file '{password_file}'"
            raise PasswordFileError(msg) from e
        except OSError as e:
            msg = f"Unexpected error reading password file '{password_file}'"
            raise PasswordFileError(msg) from e

    async def authenticate(self, *, session: Session) -> bool | None:
        """Authenticate users based on the file-stored user database."""
        authenticated = await super().authenticate(session=session)
        if authenticated:
            if not session:
                self.context.logger.debug("Authentication failure: no session provided")
                return False

            if not session.username:
                self.context.logger.debug("Authentication failure: no username provided in session")
                return None

            hash_session_username = self._users.get(session.username)
            if not hash_session_username:
                self.context.logger.debug(f"Authentication failure: no hash found for user '{session.username}'")
                return False

            if self.pwd_hasher.verify(session.password or "", hash_session_username):
                self.context.logger.debug(f"Authentication success for user '{session.username}'")
                return True

            self.context.logger.debug(f"Authentication failure: password mismatch for user '{session.username}'")
        return False

    @dataclass
    class Config:
        """Configuration for FileAuthPlugin."""

        password_file: str | Path | None = None
        """Path to file with `username:password` pairs, one per line. All passwords are encoded using sha-512."""
