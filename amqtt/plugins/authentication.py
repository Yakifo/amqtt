from dataclasses import dataclass, field
from pathlib import Path

from passlib.apps import custom_app_context as pwd_context

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
        self._allow_anonymous = self._get_config_option("allow-anonymous", True)  # noqa: FBT003

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
        """Allow empty username."""

        allow_anonymous: bool = field(default=True)


class FileAuthPlugin(BaseAuthPlugin):
    """Authentication plugin based on a file-stored user database."""

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self._users: dict[str, str] = {}
        self._read_password_file()

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
                            self._users[username] = pwd_hash
                            self.context.logger.debug(f"User '{username}' loaded")
                        else:
                            self.context.logger.warning(f"Malformed line in password file: {line}")
            self.context.logger.info(f"{len(self._users)} user(s) loaded from {password_file}")
        except FileNotFoundError:
            self.context.logger.warning(f"Password file '{password_file}' not found")
        except ValueError:
            self.context.logger.exception(f"Malformed password file '{password_file}'")
        except Exception:
            self.context.logger.exception(f"Unexpected error reading password file '{password_file}'")

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

            if pwd_context.verify(session.password, hash_session_username):
                self.context.logger.debug(f"Authentication success for user '{session.username}'")
                return True

            self.context.logger.debug(f"Authentication failure: password mismatch for user '{session.username}'")
        return False

    @dataclass
    class Config:
        """Path to the properly encoded password file."""

        password_file: str | Path | None = None
