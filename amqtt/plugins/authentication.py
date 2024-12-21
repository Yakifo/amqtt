import logging
from pathlib import Path

from passlib.apps import custom_app_context as pwd_context


class BaseAuthPlugin:
    def __init__(self, context) -> None:
        self.context = context
        try:
            self.auth_config = self.context.config["auth"]
        except KeyError:
            self.context.logger.warning(
                "'auth' section not found in context configuration",
            )

    def authenticate(self, *args, **kwargs) -> bool:
        if not self.auth_config:
            # auth config section not found
            self.context.logger.warning(
                "'auth' section not found in context configuration",
            )
            return False
        return True


class AnonymousAuthPlugin(BaseAuthPlugin):
    def __init__(self, context) -> None:
        super().__init__(context)

    async def authenticate(self, *args, **kwargs):
        authenticated = super().authenticate(*args, **kwargs)
        if authenticated:
            allow_anonymous = self.auth_config.get(
                "allow-anonymous",
                True,
            )  # allow anonymous by default
            if allow_anonymous:
                authenticated = True
                self.context.logger.debug(
                    "Authentication success: config allows anonymous",
                )
            else:
                try:
                    session = kwargs.get("session")
                    authenticated = bool(session.username)
                    if self.context.logger.isEnabledFor(logging.DEBUG):
                        if authenticated:
                            self.context.logger.debug(
                                "Authentication success: session has a non empty username",
                            )
                        else:
                            self.context.logger.debug(
                                "Authentication failure: session has an empty username",
                            )
                except KeyError:
                    self.context.logger.warning("Session information not available")
                    authenticated = False
        return authenticated


class FileAuthPlugin(BaseAuthPlugin):
    def __init__(self, context) -> None:
        super().__init__(context)
        self._users = {}
        self._read_password_file()

    def _read_password_file(self) -> None:
        password_file = self.auth_config.get("password-file", None)
        if password_file:
            try:
                with Path(password_file).open() as f:
                    self.context.logger.debug(
                        f"Reading user database from {password_file}",
                    )
                    for line in f:
                        line = line.strip()
                        if not line.startswith("#"):  # Allow comments in files
                            (username, pwd_hash) = line.split(sep=":", maxsplit=3)
                            if username:
                                self._users[username] = pwd_hash
                                self.context.logger.debug(
                                    f"user {username} , hash={pwd_hash}",
                                )
                self.context.logger.debug(
                    "%d user(s) read from file %s" % (len(self._users), password_file),
                )
            except FileNotFoundError:
                self.context.logger.warning(
                    f"Password file {password_file} not found",
                )
        else:
            self.context.logger.debug(
                "Configuration parameter 'password_file' not found",
            )

    async def authenticate(self, *args, **kwargs):
        authenticated = super().authenticate(*args, **kwargs)
        if authenticated:
            session = kwargs.get("session")
            if session.username:
                hash = self._users.get(session.username, None)
                if not hash:
                    authenticated = False
                    self.context.logger.debug(
                        f"No hash found for user '{session.username}'",
                    )
                else:
                    authenticated = pwd_context.verify(session.password, hash)
            else:
                return None
        return authenticated
