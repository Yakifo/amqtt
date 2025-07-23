import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import aiosqlite
from passlib.context import CryptContext

from amqtt.broker import BrokerContext, Broker
from amqtt.client import MQTTClient
from amqtt.contexts import Action
from amqtt.contrib.auth_db.models import AllowedTopic, PasswordHasher
from amqtt.contrib.auth_db.plugin import AuthDBPlugin
from amqtt.contrib.auth_db.managers import UserManager, TopicManager
from amqtt.errors import ConnectError, MQTTError
from amqtt.mqtt.constants import QOS_1, QOS_0
from amqtt.session import Session
from argon2 import PasswordHasher as ArgonPasswordHasher
from argon2.exceptions import VerifyMismatchError

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
@pytest.mark.asyncio
async def user_manager(password_hasher, db_connection):
    um = UserManager(db_connection)
    await um.db_sync()
    yield um


@pytest.fixture
@pytest.mark.asyncio
async def topic_manager(password_hasher, db_connection):
    tm = TopicManager(db_connection)
    await tm.db_sync()
    yield tm


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
                ph = ArgonPasswordHasher()
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
                ph = ArgonPasswordHasher()
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

    await user_manager.create_user("myuser", user_pwd)

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

    with patch.object(AuthDBPlugin, 'topic_filtering', return_value=True):

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
    with patch.object(AuthDBPlugin, 'topic_filtering', return_value=True):

        await broker.start()
        await asyncio.sleep(0.1)

        client = MQTTClient(client_id='myclientid', config={'auto_reconnect': False})
        with pytest.raises(ConnectError):
            await client.connect(f"mqtt://myuser:{client_pwd}@127.0.0.1:1883")

        await broker.shutdown()
        await asyncio.sleep(0.1)


def test_allowed_topic_match():

    at = AllowedTopic(topic="my/topic")
    assert "my/topic" in at

    at2 = AllowedTopic(topic="my/other/topic")
    assert at2 not in at

    at3 = AllowedTopic(topic="my/topic")
    assert at3 in at

    assert at == at3
    assert at != at2


def test_allowed_hash_topic_match():

    at = AllowedTopic(topic="my/#")

    at2 = AllowedTopic(topic="my/topic")
    assert "my/topic" in at
    assert at2 in at

    at3 = AllowedTopic(topic="my/other/topic")
    assert "my/other/topic" in at
    assert at3 in at

    at4 = AllowedTopic(topic="my/#")
    assert "my/#" in at
    assert at4 in at


def test_allowed_plus_topic_match():

    at = AllowedTopic(topic="my/+/topic")

    at2 = AllowedTopic(topic="my/other/topic")
    assert "my/other/topic" in at
    assert at2 in at

    at3 = AllowedTopic(topic="my/another/topic")
    assert "my/another/topic" in at
    assert at3 in at

    at4 = AllowedTopic(topic="my/+/topic")
    assert "my/+/topic" in at
    assert at4 in at

def test_allowed_topic_list_match():
    at1 = AllowedTopic(topic="my/topic")
    at2 = AllowedTopic(topic="my/other/topic")
    at3 = AllowedTopic(topic="my/another/topic")

    at_list = [at1, at2, at3]

    at4 = AllowedTopic(topic="my/topic")
    at5 = AllowedTopic(topic="my/not/topic")

    assert at4 in at_list
    assert "my/topic" in at_list

    assert at5 not in at_list
    assert "my/not/topic" not in at_list

def test_allowed_topic_hash_list_match():
    at1 = AllowedTopic(topic="my/other/#")
    at2 = AllowedTopic(topic="my/another/#")
    at3 = AllowedTopic(topic="my/not/topic")

    at_list = [at1, at2, at3]

    at4 = AllowedTopic(topic="my/other/topic")
    at5 = AllowedTopic(topic="my/other/topic/extended")

    assert at4 in at_list
    assert "my/other/topic" in at_list
    assert at5 in at_list
    assert "my/other/topic/extended" in at_list

    at6 = AllowedTopic(topic="my/negative/topic")
    assert at6 not in at_list

def test_allowed_topic_plus_list_match():
    at1 = AllowedTopic(topic="my/+/other")
    at2 = AllowedTopic(topic="my/+/another")
    at3 = AllowedTopic(topic="my/not/topic")

    at_list = [at1, at2, at3]

    at4 = AllowedTopic(topic="my/topic/other")
    at5 = AllowedTopic(topic="my/topic/another")

    assert at4 in at_list
    assert "my/topic/other" in at_list
    assert at5 in at_list
    assert "my/topic/another" in at_list

    at6 = AllowedTopic(topic="my/extended/topic/another")
    assert at6 not in at_list
    assert "my/extended/topic/another" not in at_list

def test_remove_topic_list():
    at1 = AllowedTopic(topic="my/topic")
    at2 = AllowedTopic(topic="my/other/topic")
    at3 = AllowedTopic(topic="my/another/topic")

    at_list = [at1, at2, at3]

    at4 = AllowedTopic(topic="my/topic")
    at5 = AllowedTopic(topic="my/not/topic")
    at_list.remove(at4)

    with pytest.raises(ValueError):
        at_list.remove(at5)

@pytest.mark.asyncio
async def test_add_topic_to_client(db_file, user_manager, topic_manager, db_connection):
    client_id = "myuser"
    user = await user_manager.create_user(client_id, "mypassword")
    assert user is not None

    topic_list = await topic_manager.add_topic(client_id, "my/topic", Action.PUBLISH)
    assert len(topic_list) > 0

    async with aiosqlite.connect(db_file) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        user_found = False
        async with await db_conn.execute("SELECT * FROM user_auth") as cursor:
            for row in await cursor.fetchall():
                assert row['username'] == client_id
                assert "my/topic" in row['publish_acl']
                user_found = True

        assert user_found


@pytest.mark.asyncio
async def test_remove_topic_from_client(db_file, user_manager, topic_manager, db_connection):
    client_id = "myuser"
    user = await user_manager.create_user(client_id, "mypassword")
    assert user is not None

    await topic_manager.add_topic(client_id, "my/topic", Action.PUBLISH)
    await topic_manager.add_topic(client_id, "my/other/topic", Action.PUBLISH)
    topic_list = await topic_manager.add_topic(client_id, "my/another/topic", Action.PUBLISH)
    assert len(topic_list) == 3

    async with aiosqlite.connect(db_file) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        user_found = False
        async with await db_conn.execute("SELECT * FROM user_auth") as cursor:
            for row in await cursor.fetchall():
                assert row['username'] == client_id
                assert "my/topic" in row['publish_acl']
                assert "my/other/topic" in row['publish_acl']
                assert "my/another/topic" in row['publish_acl']
                user_found = True
        assert user_found

    topic_list = await topic_manager.remove_topic(client_id, "my/other/topic", Action.PUBLISH)
    assert len(topic_list) == 2

    async with aiosqlite.connect(db_file) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        user_found = False
        async with await db_conn.execute("SELECT * FROM user_auth") as cursor:
            for row in await cursor.fetchall():
                assert row['username'] == client_id
                assert "my/topic" in row['publish_acl']
                assert "my/other/topic" not in row['publish_acl']
                assert "my/another/topic" in row['publish_acl']
                user_found = True
        assert user_found


@pytest.mark.asyncio
async def test_remove_missing_topic(db_file, user_manager, topic_manager, db_connection):
    client_id = "myuser"
    user = await user_manager.create_user(client_id, "mypassword")
    assert user is not None

    await topic_manager.add_topic(client_id, "my/topic", Action.PUBLISH)
    await topic_manager.add_topic(client_id, "my/other/topic", Action.PUBLISH)
    topic_list = await topic_manager.add_topic(client_id, "my/another/topic", Action.PUBLISH)
    assert len(topic_list) == 3

    with pytest.raises(MQTTError):
        await topic_manager.remove_topic(client_id, "my/not/topic", Action.PUBLISH)


@pytest.mark.asyncio
async def test_remove_topic_wrong_action(db_file, user_manager, topic_manager, db_connection):
    client_id = "myuser"
    user = await user_manager.create_user(client_id, "mypassword")
    assert user is not None

    await topic_manager.add_topic(client_id, "my/topic", Action.PUBLISH)
    await topic_manager.add_topic(client_id, "my/other/topic", Action.PUBLISH)
    topic_list = await topic_manager.add_topic(client_id, "my/another/topic", Action.PUBLISH)
    assert len(topic_list) == 3

    with pytest.raises(MQTTError):
        await topic_manager.remove_topic(client_id, "my/other/topic", Action.SUBSCRIBE)


@pytest.mark.parametrize("acl_topic,msg_topic,disabled,outcome", [
    ("my/topic", "my/topic", False, True),
    ("my/topic", "my/other/topic", False, False),
    ("my/topic", "my/other/topic", True, True),
])
@pytest.mark.asyncio
async def test_plugin_topic_filter_plugin(db_file, user_manager, topic_manager, db_connection, acl_topic, msg_topic, disabled, outcome):
    client_id = "myuser"
    user = await user_manager.create_user(client_id, "mypassword")
    assert user is not None

    await topic_manager.add_topic(client_id, acl_topic, Action.PUBLISH)

    broker_context = BrokerContext(broker=Broker())
    broker_context.config = AuthDBPlugin.Config(
        connection=db_connection,
        disable_topic_filtering=disabled
    )
    db_auth_plugin = AuthDBPlugin(context=broker_context)

    s = Session()
    s.username = client_id
    assert await db_auth_plugin.topic_filtering(session=s, topic=msg_topic, action=Action.PUBLISH) == outcome


@pytest.mark.parametrize("sub_topic,is_subscribed,pub_topic,msg_topic,is_disabled,is_received", [
    ("my/topic", True, "my/topic", "my/topic", False, True),
    ("my/#", True, "my/topic", "my/topic", False, True),
    # ("my/topic", True, "my/other/topic", "my/topic", False, False),
    # ("my/topic", False, "my/topic", "my/other/topic", False, False),
    # ("my/topic", True, "my/other/topic", "my/topic", True, True),
    # ("my/topic", True, "my/topic", "my/other/topic", True, True),
])
@pytest.mark.asyncio
async def test_topic_filtering(db_file, user_manager, topic_manager, db_connection, sub_topic, is_subscribed, pub_topic, msg_topic, is_disabled, is_received):

    broker_cfg = {
        'listeners': { 'default': {'type': 'tcp', 'bind': '127.0.0.1:1883'}},
        'plugins': {
            'amqtt.contrib.auth_db.AuthDBPlugin': {
                'connection': db_connection,
                'disable_topic_filtering': is_disabled
            }
        }
    }
    client_id = "myuser"

    user = await user_manager.create_user(client_id, "mypassword")
    assert user is not None
    pub_topic_list = await topic_manager.add_topic(client_id, pub_topic, Action.PUBLISH)
    assert len(pub_topic_list) > 0
    sub_topic_list = await topic_manager.add_topic(client_id, sub_topic, Action.SUBSCRIBE)
    assert len(sub_topic_list) > 0

    broker = Broker(config=broker_cfg)

    await broker.start()
    await asyncio.sleep(0.1)

    client = MQTTClient(client_id='myclientid', config={'auto_reconnect': False})
    await client.connect("mqtt://myuser:mypassword@127.0.0.1:1883")

    ret = await client.subscribe([
        (msg_topic, QOS_0)
    ])
    if is_subscribed:
        assert ret == [0x0,]
    else:
        assert ret == [0x80,]


    await asyncio.sleep(0.1)
    await client.publish(msg_topic, b"test")
    await asyncio.sleep(0.1)

    message_received = False
    try:
        message = await client.deliver_message(timeout_duration=1)
        assert message.topic == msg_topic
        message_received = True
    except asyncio.TimeoutError:
        pass

    assert message_received == is_received
    await asyncio.sleep(0.1)
    await client.disconnect()
    await asyncio.sleep(0.1)
    await broker.shutdown()


