import asyncio
import sqlite3
import tempfile

import pytest
import aiosqlite
from amqtt.broker import BrokerContext, Broker
from amqtt.client import MQTTClient
from amqtt.contrib.auth_db.plugin import AuthDBPlugin
from amqtt.contrib.auth_db.managers import UserManager
from amqtt.errors import ConnectError
from amqtt.mqtt.constants import QOS_2, QOS_1
from amqtt.session import Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

@pytest.fixture
def db_file():
    with tempfile.NamedTemporaryFile(mode='wb', delete=True) as tmp:
        yield f"{tmp}.db"


@pytest.fixture
def db_connection(db_file):
    test_db_connect = f"sqlite+aiosqlite:///{db_file}"
    yield test_db_connect


@pytest.fixture
@pytest.mark.asyncio
async def user_manager(db_connection):
    um = UserManager(db_connection)
    await um.db_sync()
    yield um

@pytest.mark.asyncio
async def test_create_user(user_manager, db_file, db_connection):
    await user_manager.create_user("myuser", "mypassword")

    async with aiosqlite.connect(db_file) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        has_user = False
        async with await db_conn.execute("SELECT * FROM user_auth") as cursor:
            for row in await cursor.fetchall():
                assert row['username'] == "myuser"
                assert row['password_hash'] != "mypassword"
                assert '$argon2' in row['password_hash']
                ph = PasswordHasher()
                ph.verify(row['password_hash'], "mypassword")

                with pytest.raises(VerifyMismatchError):
                    ph.verify(row['password_hash'], "mywrongpassword")

                has_user = True

        assert has_user, "user was not created"


@pytest.mark.asyncio
async def test_list_users(user_manager, db_file, db_connection):
    await user_manager.create_user("myuser", "mypassword")
    await user_manager.create_user("otheruser", "mypassword")
    await user_manager.create_user("anotheruser", "mypassword")

    assert len(list(await user_manager.list_users())) == 3


@pytest.mark.asyncio
async def test_list_empty_users(user_manager, db_file, db_connection):

    assert len(list(await user_manager.list_users())) == 0


@pytest.mark.asyncio
async def test_password_change(user_manager, db_file, db_connection):
    new_user = await user_manager.create_user("myuser", "mypassword")

    await user_manager.update_password("myuser", "mynewpassword")
    async with aiosqlite.connect(db_file) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        has_user = False
        async with await db_conn.execute("SELECT * FROM user_auth") as cursor:
            for row in await cursor.fetchall():
                assert row['password_hash'] != new_user._password_hash
                ph = PasswordHasher()
                with pytest.raises(VerifyMismatchError):
                    ph.verify(row['password_hash'], "mypassword")

                has_user = True

    assert has_user, "user was not found"


@pytest.mark.asyncio
async def test_remove_users(user_manager, db_file, db_connection):
    await user_manager.create_user("myuser", "mypassword")
    await user_manager.create_user("otheruser", "mypassword")
    await user_manager.create_user("anotheruser", "mypassword")

    assert len(list(await user_manager.list_users())) == 3

    await user_manager.delete_user("myuser")

    assert len(list(await user_manager.list_users())) == 2

    async with aiosqlite.connect(db_file) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        test_run = False
        async with await db_conn.execute("SELECT * FROM user_auth") as cursor:
            for row in await cursor.fetchall():
                assert row['username'] in ("otheruser", "anotheruser")
                test_run = True

        assert test_run, "users weren't not found"


@pytest.mark.parametrize("user_pwd,session_pwd,outcome", [
    ("mypassword", "mypassword", True),
    ("mypassword", "myotherpassword", False),
])
@pytest.mark.asyncio
async def test_db_auth(db_connection, user_manager, user_pwd, session_pwd, outcome):

    um = UserManager(db_connection)

    await um.db_sync()
    await um.create_user("myuser", user_pwd)

    broker_context = BrokerContext(broker=Broker())
    broker_context.config = AuthDBPlugin.Config(
        connection=db_connection
    )
    db_auth_plugin = AuthDBPlugin(context=broker_context)

    s = Session()
    s.username = "myuser"
    s.password = session_pwd

    assert await db_auth_plugin.authenticate(session=s) == outcome


@pytest.mark.asyncio
async def test_client_authentication(user_manager, db_connection):

    user = await user_manager.create_user("myuser", "mypassword")
    assert user is not None

    broker_cfg = {
        'listeners': { 'default': {'type': 'tcp', 'bind': '127.0.0.1:1883'}},
        'plugins': {
            'amqtt.contrib.auth_db.AuthDBPlugin': {
                'connection': db_connection,
            }
        }
    }

    broker = Broker(config=broker_cfg)
    await broker.start()
    await asyncio.sleep(0.1)

    client = MQTTClient(client_id='myclientid', config={'auto_reconnect': False})
    await client.connect("mqtt://myuser:mypassword@127.0.0.1:1883")

    await client.subscribe([
        ("my/topic", QOS_1)
    ])
    await asyncio.sleep(0.1)
    await client.publish("my/topic", b"test")
    await asyncio.sleep(0.1)
    message = await client.deliver_message(timeout_duration=1)
    assert message.topic == "my/topic"
    await asyncio.sleep(0.1)
    await client.disconnect()
    await asyncio.sleep(0.1)
    await broker.shutdown()


@pytest.mark.parametrize("client_pwd", [
    ("mywrongpassword", ),
    ("", ),
])
@pytest.mark.asyncio
async def test_client_blocked(user_manager, db_connection, client_pwd):

    user = await user_manager.create_user("myuser", "mypassword")
    assert user is not None

    broker_cfg = {
        'listeners': { 'default': {'type': 'tcp', 'bind': '127.0.0.1:1883'}},
        'plugins': {
            'amqtt.contrib.auth_db.AuthDBPlugin': {
                'connection': db_connection,
            }
        }
    }

    broker = Broker(config=broker_cfg)
    await broker.start()
    await asyncio.sleep(0.1)

    client = MQTTClient(client_id='myclientid', config={'auto_reconnect': False})
    with pytest.raises(ConnectError):
        await client.connect(f"mqtt://myuser:{client_pwd}@127.0.0.1:1883")

    await broker.shutdown()
    await asyncio.sleep(0.1)

