import asyncio
import logging
import tempfile
from pathlib import Path

import pytest
from passlib.context import CryptContext
from typer.testing import CliRunner

from amqtt.contexts import Action
from amqtt.contrib.auth_db.managers import TopicManager, UserManager
from amqtt.contrib.auth_db.models import PasswordHasher, AllowedTopic
from amqtt.contrib.auth_db.topic_mgr_cli import topic_app
from amqtt.contrib.auth_db.user_mgr_cli import user_app

runner = CliRunner()

@pytest.fixture
def password_hasher():
    pwd_hasher = PasswordHasher()
    pwd_hasher.crypt_context = CryptContext(schemes=["argon2", ], deprecated="auto")
    yield pwd_hasher


@pytest.fixture
def db_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        with tempfile.NamedTemporaryFile(mode='wb', delete=True) as tmp:
            yield Path(temp_dir) / f"{tmp.name}.db"


@pytest.fixture
def db_connection(db_file):
    test_db_connect = f"sqlite+aiosqlite:///{db_file}"
    yield test_db_connect


@pytest.fixture
async def user_manager(password_hasher, db_connection):
    um = UserManager(db_connection)
    await um.db_sync()
    yield um


@pytest.fixture
async def topic_manager(password_hasher, db_connection):
    tm = TopicManager(db_connection)
    await tm.db_sync()
    yield tm


@pytest.mark.parametrize("app,error_msg", [
    (user_app, "user cli"),
    (topic_app, "topic cli"),
])
def test_cli_mgr_no_params(app, error_msg):

    result = runner.invoke(app, [])
    assert result.exit_code == 0, f"{result.output}"


@pytest.mark.parametrize("app,error_msg", [
    (user_app, "user cli"),
    (topic_app, "topic cli"),
])
def test_cli_mgr_no_db_type(app, error_msg):
    result = runner.invoke(topic_app, ["sync"])
    assert result.exit_code == 2


@pytest.mark.parametrize("app,error_msg", [
    (user_app, "user cli"),
    (topic_app, "topic cli"),
])
def test_cli_mgr_no_db_username(app, error_msg, caplog):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(app, ["-d", "mysql", "sync"])
        assert result.exit_code == 1
        assert "DB access requires a username be provided." in caplog.text


@pytest.mark.parametrize("app,error_msg", [
    (user_app, "user cli"),
    (topic_app, "topic cli"),
])
def test_cli_mgr_db_not_installed(app, error_msg, caplog):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(app,
                               ["-d", "mysql", "-u", "mydbname", "sync",],
                               input="mydbpassword\n"
                               )
        assert result.exit_code == 1
        assert isinstance(result.exception, ModuleNotFoundError)


@pytest.mark.parametrize("app,error_msg", [
    (user_app, "user cli"),
    (topic_app, "topic cli"),
])
def test_cli_mgr_sync(db_file, app, error_msg, caplog):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "sync"
        ])
        assert result.exit_code == 0
        assert "Success: database synced." in caplog.text


@pytest.mark.parametrize("app,success_msg", [
    (user_app, "authentications"),
    (topic_app, "authorizations"),
])
def test_topic_empty_list(db_file, topic_manager, caplog, app, success_msg):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "list"
        ])
        assert result.exit_code == 0
        assert f"No client {success_msg} exist." in caplog.text


def test_user_mgr_list_clients(db_file, user_manager, caplog):
    async def init_user_auths():
        await user_manager.create_user_auth("client123", "randompassword")
        await user_manager.create_user_auth("client456", "randompassword")

    asyncio.run(init_user_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "list"
        ])
        assert result.exit_code == 0

        info_records = [record for record in caplog.records if record.levelname == "INFO"]

        assert 'client123' in info_records[0].message
        assert 'client456' in info_records[1].message


def test_topic_mgr_list_clients(db_file, topic_manager, caplog):
    async def init_topic_auths():
        await topic_manager.create_topic_auth('device123')
        await topic_manager.create_topic_auth('device456')
        await topic_manager.add_allowed_topic('device123', 'my/topic', Action.SUBSCRIBE)
        await topic_manager.add_allowed_topic('device456', 'my/topic', Action.PUBLISH)

    asyncio.run(init_topic_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(topic_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "list"
        ])
        assert result.exit_code == 0

        info_records = [record for record in caplog.records if record.levelname == "INFO"]

        assert 'device123' in info_records[0].message
        assert 'my/topic' in info_records[0].message
        assert 'device456' in info_records[1].message
        assert 'my/topic' in info_records[1].message


def test_user_mgr_add_auth_missing_param(db_file, user_manager, caplog):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "add"
        ])
        assert result.exit_code == 2


def test_add_allowed_topic_missing_param(db_file, topic_manager, caplog):

    with caplog.at_level(logging.INFO):
        result = runner.invoke(topic_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "add", "-c", "client123", "my/topic"
        ])
        assert result.exit_code == 2


def test_user_mgr_add_auth_missing_password(db_file, user_manager, caplog):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "add", "-c", 'client123'
        ], input=" \n")
        assert result.exit_code == 1
        assert "Error: client password cannot be empty." in caplog.text, caplog.text

    async def verify_add():
        user_auth = await user_manager.get_user_auth('client123')
        assert user_auth is None

    asyncio.run(verify_add())


def test_user_mgr_add_auth(db_file, user_manager, caplog):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "add", "-c", 'client123'
        ], input="dbpassword\nuserpassword\n")
        assert result.exit_code == 0
        assert "Success: created 'client123'" in caplog.text, caplog.text

    async def verify_add():
        user_auth = await user_manager.get_user_auth('client123')
        assert user_auth is not None

    asyncio.run(verify_add())


def test_add_allowed_topic(db_file, topic_manager, caplog):
    with caplog.at_level(logging.INFO):
        result = runner.invoke(topic_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "add",
            "-c", "client123",
            "-a", "publish",
            "my/topic"
        ])
        assert result.exit_code == 0
        assert "Success: topic 'my/topic' added to publish for 'client123'" in caplog.text

    async def verify_add():
        topic_auth = await topic_manager.get_topic_auth('client123')
        assert topic_auth is not None
        assert AllowedTopic('my/topic') in topic_auth.publish_acl

    asyncio.run(verify_add())


def test_remove_user_auth_mismatch(db_file, user_manager, caplog):
    async def init_user_auths():
        await user_manager.create_user_auth("client123", "randompassword")

    asyncio.run(init_user_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "rm",
            "-c", "device123",
        ])
        assert result.exit_code == 1, caplog.text
        assert "Error: client 'device123' does not exist." in caplog.text, result.output


def test_remove_allowed_topic_mismatch(db_file, topic_manager, caplog):
    async def init_topic_auths():
        await topic_manager.create_topic_auth('device123')
        await topic_manager.add_allowed_topic('device123', 'my/topic', Action.SUBSCRIBE)

    asyncio.run(init_topic_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(topic_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "rm",
            "-c", "device123",
            "-a", "publish",
            "my/topic"
        ])
        assert result.exit_code == 1, caplog.text
        assert "Error: topic 'my/topic' not in the publish allow list for device123." in caplog.text


def test_remove_user_auth_abort(db_file, user_manager, caplog):
    async def init_user_auths():
        await user_manager.create_user_auth("client123", "randompassword")

    asyncio.run(init_user_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "rm",
            "-c", "client123",
        ], input="N\n")
        assert result.exit_code == 0, caplog.text

    async def verify_user_exists():
        assert await user_manager.get_user_auth('client123') is not None

    asyncio.run(verify_user_exists())


def test_remove_user_auth_confirm(db_file, user_manager, caplog):
    async def init_user_auths():
        await user_manager.create_user_auth("client123", "randompassword")

    asyncio.run(init_user_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "rm",
            "-c", "client123",
        ], input="y\n")
        assert result.exit_code == 0, caplog.text
        assert "Success: 'client123' was removed." in caplog.text, result.output

    async def verify_user_removed():
        assert await user_manager.get_user_auth('client123') is None

    asyncio.run(verify_user_removed())


def test_remove_allowed_topic(db_file, topic_manager, caplog):
    async def init_topic_auth():
        await topic_manager.create_topic_auth('device123')
        await topic_manager.add_allowed_topic('device123', 'my/topic', Action.SUBSCRIBE)

    asyncio.run(init_topic_auth())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(topic_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "rm",
            "-c", "device123",
            "-a", "subscribe",
            "my/topic"
        ])
        assert result.exit_code == 0
        assert "Success: removed topic 'my/topic' from subscribe for 'device123'" in caplog.text, caplog.text


def test_user_mgr_change_password_empty(db_file, user_manager, caplog):
    async def init_user_auths():
        await user_manager.create_user_auth("client123", "randompassword")

    asyncio.run(init_user_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "pwd",
            "-c", "client123",
        ], input=" \n")
        assert result.exit_code == 1, caplog.text
        assert "Error: client password cannot be empty." in caplog.text, caplog.text


def test_user_mgr_change_password(db_file, user_manager, caplog):
    async def init_user_auths():
        await user_manager.create_user_auth("client123", "randompassword")
        user_auth = await user_manager.get_user_auth('client123')
        return user_auth._password_hash

    orig_pwd_hash = asyncio.run(init_user_auths())

    with caplog.at_level(logging.INFO):
        result = runner.invoke(user_app, [
            "-d", "sqlite",
            "-f", f"{db_file}",
            "pwd",
            "-c", "client123",
        ], input="myotherpassword\n")
        assert result.exit_code == 0, caplog.text
        assert "Success: client 'client123' password updated." in caplog.text, caplog.text

    async def verify_user_exists(pwd_hash):
        user_auth = await user_manager.get_user_auth('client123')
        assert user_auth is not None
        assert user_auth._password_hash != pwd_hash

    asyncio.run(verify_user_exists(orig_pwd_hash))

@pytest.mark.asyncio
async def test_user_mgr_cli():
    cmd = [
        "user_mgr",
        "--help"]

    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await asyncio.sleep(0.2)
    stdout, stderr = await proc.communicate()

    assert proc.returncode == 0, f"user_mgr error code: {proc.returncode} - {stdout} - {stderr}"


@pytest.mark.asyncio
async def test_topic_mgr_cli():
    cmd = [
        "topic_mgr",
        "--help"]

    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await asyncio.sleep(0.2)
    stdout, stderr = await proc.communicate()

    assert proc.returncode == 0, f"topic_mgr error code: {proc.returncode} - {stdout} - {stderr}"
