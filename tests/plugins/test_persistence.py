import asyncio
import logging
from pathlib import Path
import sqlite3
import pytest
import aiosqlite

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

from amqtt.broker import Broker, BrokerContext, RetainedApplicationMessage
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0, QOS_1
from amqtt.plugins.persistence import SessionDBPlugin, Subscription, StoredSession, RetainedMessage, \
    StoredMessage
from amqtt.session import Session

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)

logger = logging.getLogger(__name__)

@pytest.fixture
async def db_file():
    db_file = Path(__file__).parent / "amqtt.db"
    yield db_file
    if db_file.exists():
        db_file.unlink()

@pytest.fixture
async def broker_context():
    cfg = {
        'listeners': { 'default': {'type': 'tcp', 'bind': 'localhost:1883' }},
        'plugins': {}
    }

    context = BrokerContext(broker=Broker(config=cfg))
    yield context

@pytest.fixture
async def db_session_factory(db_file):
    engine = create_async_engine(f"sqlite+aiosqlite:///{str(db_file)}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory



@pytest.mark.asyncio
async def test_initialize_tables(db_file, broker_context):

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    assert db_file.exists()

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    table_name = 'stored_sessions'
    cursor.execute(f"PRAGMA table_info({table_name});")
    rows = cursor.fetchall()
    column_names = [row[1] for row in rows]
    assert len(column_names) > 1

@pytest.mark.asyncio
async def test_create_stored_session(db_file, broker_context, db_session_factory):

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    async with db_session_factory() as db_session:
        async with db_session.begin():
            stored_session = await session_db_plugin._get_or_create_session(db_session, 'test_client_1')
            assert stored_session.client_id == 'test_client_1'

    async with aiosqlite.connect(str(db_file)) as db:
        async with await db.execute("SELECT * FROM stored_sessions") as cursor:
            async for row in cursor:
                assert row[1] == 'test_client_1'

@pytest.mark.asyncio
async def test_get_stored_session(db_file, broker_context, db_session_factory):
    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    async with aiosqlite.connect(str(db_file)) as db:
        sql = """INSERT INTO stored_sessions (
    client_id, clean_session, will_flag,
    will_qos, keep_alive,
    retained, subscriptions
) VALUES (
    'test_client_1',
    1,
    0,
    1,
    60,
    '[]',
    '[{"topic":"sensors/#","qos":1}]'
)"""
        await db.execute(sql)
        await db.commit()

    async with db_session_factory() as db_session:
        async with db_session.begin():
            stored_session = await session_db_plugin._get_or_create_session(db_session, 'test_client_1')
            assert stored_session.subscriptions == [Subscription(topic='sensors/#', qos=1)]


@pytest.mark.asyncio
async def test_update_stored_session(db_file, broker_context, db_session_factory):
    broker_context.config = SessionDBPlugin.Config(file=db_file)

    # create session for client id (without subscription)
    await broker_context.add_subscription('test_client_1', None, None)

    session = broker_context.get_session('test_client_1')
    assert session is not None
    session.clean_session = True

    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    # initialize with stored client session
    async with aiosqlite.connect(str(db_file)) as db:
        sql = """INSERT INTO stored_sessions (
    client_id, clean_session, will_flag,
    will_qos, keep_alive,
    retained, subscriptions
) VALUES (
    'test_client_1',
    1,
    0,
    1,
    60,
    '[]',
    '[{"topic":"sensors/#","qos":1}]'
)"""
        await db.execute(sql)
        await db.commit()

    await session_db_plugin.on_broker_client_subscribed(client_id='test_client_1', topic='my/topic', qos=2)

    # verify that the stored session has been updated with the new subscription
    has_stored_session = False
    async with aiosqlite.connect(str(db_file)) as db:
        async with await db.execute("SELECT * FROM stored_sessions") as cursor:
            async for row in cursor:
                assert row[1] == 'test_client_1'
                assert row[-1] == '[{"topic": "sensors/#", "qos": 1}, {"topic": "my/topic", "qos": 2}]'
                has_stored_session = True
    assert has_stored_session, "stored session wasn't updated"


@pytest.mark.asyncio
async def test_client_connected_with_clean_session(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    session = Session()
    session.client_id = 'test_client_connected'
    session.is_anonymous = False
    session.clean_session = True

    await session_db_plugin.on_broker_client_connected(client_id='test_client_connected', client_session=session)

    async with aiosqlite.connect(str(db_file)) as db_conn:
        db_conn.row_factory = sqlite3.Row

        async with await db_conn.execute("SELECT * FROM stored_sessions") as cursor:
            assert len(await cursor.fetchall()) == 0


@pytest.mark.asyncio
async def test_client_connected_anonymous_session(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    session = Session()
    session.is_anonymous = True
    session.client_id = 'test_client_connected'

    await session_db_plugin.on_broker_client_connected(client_id='test_client_connected', client_session=session)

    async with aiosqlite.connect(str(db_file)) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory
        async with await db_conn.execute("SELECT * FROM stored_sessions") as cursor:
            assert len(await cursor.fetchall()) == 0


@pytest.mark.asyncio
async def test_client_connected_and_stored_session(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    session = Session()
    session.client_id = 'test_client_connected'
    session.is_anonymous = False
    session.clean_session = False
    session.will_flag = True
    session.will_qos = 1
    session.will_topic = 'my/will/topic'
    session.will_retain = False
    session.will_message = b'test connected client has a last will (and testament) message'
    session.keep_alive = 42

    await session_db_plugin.on_broker_client_connected(client_id='test_client_connected', client_session=session)

    has_stored_session = False
    async with aiosqlite.connect(str(db_file)) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        async with await db_conn.execute("SELECT * FROM stored_sessions") as cursor:
            for row in await cursor.fetchall():
                assert row['client_id'] == 'test_client_connected'
                assert row['clean_session'] == False
                assert row['will_flag'] == True
                assert row['will_qos'] == 1
                assert row['will_topic'] == 'my/will/topic'
                assert row['will_retain'] == False
                assert row['will_message'] == b'test connected client has a last will (and testament) message'
                assert row['keep_alive'] == 42
                has_stored_session = True
    assert has_stored_session, "client session wasn't stored"


@pytest.mark.asyncio
async def test_repopulate_stored_sessions(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    async with aiosqlite.connect(str(db_file)) as db:
        sql = """INSERT INTO stored_sessions (
        client_id, clean_session, will_flag,
        will_qos, keep_alive,
        retained, subscriptions
    ) VALUES (
        'test_client_1',
        1,
        0,
        1,
        60,
        '[{"topic":"sensors/#","data":"this message is retained when client reconnects","qos":1}]',
        '[{"topic":"sensors/#","qos":1}]'
    )"""
        await db.execute(sql)
        await db.commit()

    await session_db_plugin.on_broker_post_start()

    session = broker_context.get_session('test_client_1')
    assert session is not None
    assert session.retained_messages.qsize() == 1

    assert 'sensors/#' in broker_context._broker_instance._subscriptions

    # ugly: b/c _subscriptions is a list of dictionaries of tuples
    assert broker_context._broker_instance._subscriptions['sensors/#'][0][1] == 1


@pytest.mark.asyncio
async def test_client_retained_message(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    # add a session to the broker
    await broker_context.add_subscription('test_retained_client', None, None)

    # update the session so that it's retained
    session = broker_context.get_session('test_retained_client')
    assert session is not None
    session.is_anonymous = False
    session.clean_session = False
    session.transitions.disconnect()

    retained_message = RetainedApplicationMessage(source_session=session, topic='my/retained/topic', data=b'retain message for disconnected client', qos=2)
    await session_db_plugin.on_broker_retained_message(client_id='test_retained_client', retained_message=retained_message)

    async with db_session_factory() as db_session:
        async with db_session.begin():
            stmt = select(StoredSession).filter(StoredSession.client_id == 'test_retained_client')
            stored_session = await db_session.scalar(stmt)
            assert stored_session is not None
            assert len(stored_session.retained) > 0
            assert RetainedMessage(topic='my/retained/topic', data='retained message', qos=2)


@pytest.mark.asyncio
async def test_topic_retained_message(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file, clear_on_shutdown=False)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    # add a session to the broker
    await broker_context.add_subscription('test_retained_client', None, None)

    # update the session so that it's retained
    session = broker_context.get_session('test_retained_client')
    assert session is not None
    session.is_anonymous = False
    session.clean_session = False
    session.transitions.disconnect()

    retained_message = RetainedApplicationMessage(source_session=session, topic='my/retained/topic', data=b'retained message', qos=2)
    await session_db_plugin.on_broker_retained_message(client_id=None, retained_message=retained_message)

    has_stored_message = False
    async with aiosqlite.connect(str(db_file)) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        async with await db_conn.execute("SELECT * FROM stored_messages") as cursor:
            # assert(len(await cursor.fetchall()) > 0)
            for row in await cursor.fetchall():
                assert row['topic'] == 'my/retained/topic'
                assert row['data'] == b'retained message'
                assert row['qos'] == 2
                has_stored_message = True

    assert has_stored_message, "retained topic message wasn't stored"


@pytest.mark.asyncio
async def test_topic_clear_retained_message(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    # add a session to the broker
    await broker_context.add_subscription('test_retained_client', None, None)

    # update the session so that it's retained
    session = broker_context.get_session('test_retained_client')
    assert session is not None
    session.is_anonymous = False
    session.clean_session = False
    session.transitions.disconnect()

    retained_message = RetainedApplicationMessage(source_session=session, topic='my/retained/topic', data=b'', qos=0)
    await session_db_plugin.on_broker_retained_message(client_id=None, retained_message=retained_message)

    async with aiosqlite.connect(str(db_file)) as db_conn:
        db_conn.row_factory = sqlite3.Row

        async with await db_conn.execute("SELECT * FROM stored_messages") as cursor:
            assert(len(await cursor.fetchall()) == 0)


@pytest.mark.asyncio
async def test_restoring_retained_message(db_file, broker_context, db_session_factory) -> None:

    broker_context.config = SessionDBPlugin.Config(file=db_file)
    session_db_plugin = SessionDBPlugin(broker_context)
    await session_db_plugin.on_broker_pre_start()

    stmts = ("INSERT INTO stored_messages VALUES(1,'my/retained/topic1',X'72657461696e6564206d657373616765',2)",
             "INSERT INTO stored_messages VALUES(2,'my/retained/topic2',X'72657461696e6564206d65737361676532',2)",
             "INSERT INTO stored_messages VALUES(3,'my/retained/topic3',X'72657461696e6564206d65737361676533',2)")

    async with aiosqlite.connect(str(db_file)) as db:
        for stmt in stmts:
            await db.execute(stmt)
        await db.commit()

    await session_db_plugin.on_broker_post_start()

    assert len(broker_context.retained_messages) == 3
    assert 'my/retained/topic1' in broker_context.retained_messages
    assert 'my/retained/topic2' in broker_context.retained_messages
    assert 'my/retained/topic3' in broker_context.retained_messages


# @pytest.mark.asyncio
# async def test_full_broker_and_client() -> None:
#
#     cfg = {
#         'listeners': {
#             'default': {
#                 'type': 'tcp',
#                 'bind': '127.0.0.1:1883'
#             }
#         },
#         'plugins': {
#             'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': False},
#             'amqtt.plugins.persistence.SessionDBPlugin': {
#                 'clean_on_shutdown': False,
#             }
#         }
#     }
#
#     b = Broker(config=cfg)
#     await b.start()
#     await asyncio.sleep(1)
#
#     c1 = MQTTClient(client_id='test_client1', config={'auto_reconnect':False})
#     await c1.connect("mqtt://myUsername@127.0.0.1:1883", cleansession=False)
#
#     await c1.publish("my/topic", b'my retained message', retain=True)
#     await c1.disconnect()
