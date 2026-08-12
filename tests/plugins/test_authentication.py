import asyncio
from contextlib import suppress
import logging
from pathlib import Path

import pytest
from pwdlib.exceptions import UnknownHashError

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.contexts import BaseContext
from amqtt.errors import ConnectError
from amqtt.plugins import authentication as authentication_module
from amqtt.plugins.authentication import (
    AnonymousAuthPlugin,
    DeprecatedSHA512CryptHasher,
    FileAuthPlugin,
    PasswordFileError,
    _ensure_str,
)
from amqtt.plugins.base import BaseAuthPlugin
from amqtt.session import Session

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)

PASSWORD_FILE = Path(__file__).parent / "passwd"
LEGACY_PASSWORD_FILE = Path(__file__).parent / "pass512"


def _testlog_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == "testlog"]


def _context(config: object, logger_name: str = __name__) -> BaseContext:
    context = BaseContext()
    context.logger = logging.getLogger(logger_name)
    context.config = config
    return context


def _session(username: str | None = None, password: str | None = None) -> Session:
    session = Session()
    session.username = username
    session.password = password
    return session


def _first_hash(password_file: Path = PASSWORD_FILE) -> str:
    for line in password_file.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            return line.split(":", maxsplit=1)[1]
    raise AssertionError(f"No password hash found in {password_file}")


class RaisingPasswordFile:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def open(self, *args: object, **kwargs: object) -> object:
        raise self.exc

    def __str__(self) -> str:
        return "raising-password-file"


@pytest.mark.asyncio
async def test_base_no_config(caplog: pytest.LogCaptureFixture) -> None:
    """Check BaseTopicPlugin returns false if no topic-check is present."""
    with caplog.at_level(logging.DEBUG, logger="testlog"):
        context = _context({}, "testlog")

        plugin = BaseAuthPlugin(context)
        authorised = await plugin.authenticate(session=Session())
        assert authorised is False

    # Warning messages are only generated if using deprecated plugin configuration on initial load
    log_records = _testlog_records(caplog)
    assert len(log_records) == 1
    assert log_records[0].levelno == logging.WARNING
    assert log_records[0].message == "'auth' section not found in context configuration"


@pytest.mark.parametrize(
    "config",
    [
        {"auth": {"allow-anonymous": True}},
        AnonymousAuthPlugin.Config(allow_anonymous=True),
    ],
)
@pytest.mark.asyncio
async def test_anonymous_auth_allows_anonymous_sessions(config: object) -> None:
    session = _session("")

    auth_plugin = AnonymousAuthPlugin(_context(config))

    assert await auth_plugin.authenticate(session=session) is True
    assert session.is_anonymous is True


@pytest.mark.asyncio
async def test_anonymous_auth_disallows_missing_username_when_disabled() -> None:
    session = _session("")
    auth_plugin = AnonymousAuthPlugin(_context({"auth": {"allow-anonymous": False}}))

    assert await auth_plugin.authenticate(session=session) is False
    assert session.is_anonymous is False


@pytest.mark.asyncio
async def test_anonymous_auth_allows_username_when_anonymous_is_disabled() -> None:
    session = _session("test")
    auth_plugin = AnonymousAuthPlugin(_context({"auth": {"allow-anonymous": False}}))

    assert await auth_plugin.authenticate(session=session) is True
    assert session.is_anonymous is False


@pytest.mark.asyncio
async def test_anonymous_auth_returns_false_when_base_auth_is_disabled() -> None:
    session = _session("")
    auth_plugin = AnonymousAuthPlugin(_context({}))

    assert await auth_plugin.authenticate(session=session) is False


def test_ensure_str_decodes_bytes_and_preserves_strings() -> None:
    assert _ensure_str(b"value") == "value"
    assert _ensure_str("value") == "value"


def test_deprecated_sha512_hasher_identify_handles_valid_invalid_and_bad_bytes() -> None:
    assert DeprecatedSHA512CryptHasher.identify("$6$salt$hash") is True
    assert DeprecatedSHA512CryptHasher.identify(b"$6$salt$hash") is True
    assert DeprecatedSHA512CryptHasher.identify("$argon2id$hash") is False
    assert DeprecatedSHA512CryptHasher.identify(b"\xff") is False


def test_deprecated_sha512_hasher_metadata_and_hashing_disabled() -> None:
    hasher = DeprecatedSHA512CryptHasher()

    assert hasher.name == "sha512_crypt"
    assert hasher.check_needs_rehash("$6$salt$hash") is True
    with pytest.raises(NotImplementedError, match="Generating new sha512_crypt hashes is disabled"):
        hasher.hash("password")


def test_deprecated_sha512_verify_denies_when_native_crypt_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = DeprecatedSHA512CryptHasher()
    monkeypatch.setattr(authentication_module, "_native_crypt", None)

    with pytest.warns(RuntimeWarning, match="native 'crypt' module"):
        assert hasher.verify("password", "$6$salt$hash") is False


def test_deprecated_sha512_verify_rejects_non_sha512_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = DeprecatedSHA512CryptHasher()

    def fail_if_called(password: str, password_hash: str) -> str:
        raise AssertionError(f"crypt should not be called for {password}:{password_hash}")

    monkeypatch.setattr(authentication_module, "_native_crypt", fail_if_called)

    assert hasher.verify("password", "$argon2id$hash") is False


def test_deprecated_sha512_verify_compares_native_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = DeprecatedSHA512CryptHasher()

    def fake_crypt(password: str, password_hash: str) -> str:
        assert password == "test"
        return password_hash

    monkeypatch.setattr(authentication_module, "_native_crypt", fake_crypt)

    with pytest.warns(DeprecationWarning, match="legacy 'sha512_crypt'"):
        assert hasher.verify(b"test", b"$6$salt$hash") is True


def test_deprecated_sha512_verify_handles_native_crypt_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = DeprecatedSHA512CryptHasher()
    monkeypatch.setattr(authentication_module, "_native_crypt", lambda password, password_hash: "$6$salt$different")

    with pytest.warns(DeprecationWarning, match="legacy 'sha512_crypt'"):
        assert hasher.verify("test", "$6$salt$hash") is False


def test_deprecated_sha512_verify_handles_native_crypt_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = DeprecatedSHA512CryptHasher()
    monkeypatch.setattr(authentication_module, "_native_crypt", lambda password, password_hash: None)

    with pytest.warns(DeprecationWarning, match="legacy 'sha512_crypt'"):
        assert hasher.verify("test", "$6$salt$hash") is False


def test_deprecated_sha512_verify_handles_decode_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = DeprecatedSHA512CryptHasher()
    monkeypatch.setattr(authentication_module, "_native_crypt", lambda password, password_hash: password_hash)

    assert hasher.verify("test", b"\xff") is False


def test_deprecated_sha512_verify_handles_native_crypt_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = DeprecatedSHA512CryptHasher()

    def fake_crypt(password: str, password_hash: str) -> str:
        raise ValueError("bad crypt config")

    monkeypatch.setattr(authentication_module, "_native_crypt", fake_crypt)

    with pytest.warns(DeprecationWarning, match="legacy 'sha512_crypt'"):
        assert hasher.verify("test", "$6$salt$hash") is False


def test_file_auth_no_password_file_config_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=__name__):
        auth_plugin = FileAuthPlugin(_context({"auth": {}}))

    assert auth_plugin._users == {}
    assert "Configuration parameter 'password-file' not found" in caplog.text


def test_file_auth_loads_password_file_from_dataclass_config() -> None:
    auth_plugin = FileAuthPlugin(_context(FileAuthPlugin.Config(password_file=PASSWORD_FILE)))

    assert "user" in auth_plugin._users


def test_file_auth_loads_string_path_and_ignores_comments_blanks_and_malformed_lines(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    password_file = tmp_path / "passwd"
    password_file.write_text(
        f"""
# comment

malformed
user:{_first_hash()}
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger=__name__):
        auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": str(password_file)}}))

    assert auth_plugin._users == {"user": _first_hash()}
    assert "Malformed line in password file: malformed" in caplog.text


def test_file_auth_warns_when_loading_legacy_sha512_hashes() -> None:
    with pytest.warns(DeprecationWarning, match="sha512"):
        auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": LEGACY_PASSWORD_FILE}}))

    assert "user" in auth_plugin._users


def test_file_auth_wraps_missing_password_file_errors(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing-passwd"

    with pytest.raises(PasswordFileError, match="not found"):
        FileAuthPlugin(_context({"auth": {"password-file": missing_file}}))


def test_file_auth_wraps_unknown_hash_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    password_file = tmp_path / "passwd"
    password_file.write_text("user:unsupported\n", encoding="utf-8")

    def raise_unknown_hash(cls: type[DeprecatedSHA512CryptHasher], password_hash: str | bytes) -> bool:
        raise UnknownHashError(password_hash)

    monkeypatch.setattr(DeprecatedSHA512CryptHasher, "identify", classmethod(raise_unknown_hash))

    with pytest.raises(PasswordFileError, match="Unsupported hash format"):
        FileAuthPlugin(_context({"auth": {"password-file": password_file}}))


def test_file_auth_wraps_malformed_password_file_errors() -> None:
    password_file = RaisingPasswordFile(ValueError("bad password file"))

    with pytest.raises(PasswordFileError, match="Malformed password file"):
        FileAuthPlugin(_context({"auth": {"password-file": password_file}}))


def test_file_auth_wraps_unexpected_os_errors() -> None:
    password_file = RaisingPasswordFile(OSError("permission denied"))

    with pytest.raises(PasswordFileError, match="Unexpected error reading password file"):
        FileAuthPlugin(_context({"auth": {"password-file": password_file}}))


def test_file_auth_reports_hash_support() -> None:
    auth_plugin = FileAuthPlugin(_context(FileAuthPlugin.Config()))

    assert auth_plugin.is_hash_supported(_first_hash()) is True
    assert auth_plugin.is_hash_supported("$6$salt$hash") is True
    assert auth_plugin.is_hash_supported("plaintext") is False


@pytest.mark.asyncio
async def test_file_auth_allows_matching_password() -> None:
    auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": PASSWORD_FILE}}))

    assert await auth_plugin.authenticate(session=_session("user", "test")) is True


@pytest.mark.asyncio
async def test_file_auth_rejects_wrong_password() -> None:
    auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": PASSWORD_FILE}}))

    assert await auth_plugin.authenticate(session=_session("user", "wrong password")) is False


@pytest.mark.asyncio
async def test_file_auth_rejects_unknown_user() -> None:
    auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": PASSWORD_FILE}}))

    assert await auth_plugin.authenticate(session=_session("some user", "some password")) is False


@pytest.mark.asyncio
async def test_file_auth_returns_false_without_session() -> None:
    auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": PASSWORD_FILE}}))

    assert await auth_plugin.authenticate(session=None) is False


@pytest.mark.asyncio
async def test_file_auth_returns_none_without_username() -> None:
    auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": PASSWORD_FILE}}))

    assert await auth_plugin.authenticate(session=_session("", "password")) is None


@pytest.mark.asyncio
async def test_file_auth_returns_false_when_base_auth_is_disabled() -> None:
    auth_plugin = FileAuthPlugin(_context({}))

    assert await auth_plugin.authenticate(session=_session("user", "test")) is False


@pytest.mark.asyncio
async def test_file_auth_authenticates_legacy_sha512_when_native_crypt_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_crypt(password: str, password_hash: str) -> str:
        assert password == "test"
        return password_hash

    monkeypatch.setattr(authentication_module, "_native_crypt", fake_crypt)

    with pytest.warns(DeprecationWarning, match="sha512"):
        auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": LEGACY_PASSWORD_FILE}}))

    with pytest.warns(DeprecationWarning, match="legacy 'sha512_crypt'"):
        assert await auth_plugin.authenticate(session=_session("user", "test")) is True


@pytest.mark.asyncio
async def test_file_auth_denies_legacy_sha512_when_native_crypt_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authentication_module, "_native_crypt", None)

    with pytest.warns(DeprecationWarning, match="sha512"):
        auth_plugin = FileAuthPlugin(_context({"auth": {"password-file": LEGACY_PASSWORD_FILE}}))

    with pytest.warns(RuntimeWarning, match="native 'crypt' module"):
        assert await auth_plugin.authenticate(session=_session("user", "test")) is False


@pytest.mark.asyncio
async def test_connack_failure_on_invalid_password(unused_tcp_port: int) -> None:
    bind = f"127.0.0.1:{unused_tcp_port}"
    config = {
        "listeners": {
            "default": {"type": "tcp", "bind": bind, "max_connections": 10},
        },
        "plugins": [
            {"amqtt.plugins.authentication.FileAuthPlugin": {"password_file": PASSWORD_FILE}},
        ],
    }

    broker = Broker(config=config)
    client = MQTTClient(config={"auto_reconnect": False})

    await broker.start()
    await asyncio.sleep(0.1)

    try:
        with pytest.raises(ConnectError) as exc:
            await client.connect(f"mqtt://user:badpass@{bind}/")

        assert exc.value.return_code == 0x05
    finally:
        with suppress(Exception):
            await client.disconnect()
        await broker.shutdown()
        await asyncio.sleep(0.1)
