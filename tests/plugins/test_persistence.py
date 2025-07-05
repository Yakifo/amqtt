import asyncio
import logging
from pathlib import Path
import sqlite3
import pytest
import aiosqlite

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from amqtt.broker import Broker, BrokerContext
from amqtt.plugins.persistence import SessionDBPlugin, Subscription

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)

logger = logging.getLogger(__name__)

@pytest.fixture
async def db_file():
    db_file = Path(__file__).parent / "amqtt.lite"
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
            stored_session = await session_db_plugin._get_or_create(db_session, 'test_client_1')
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
            stored_session = await session_db_plugin._get_or_create(db_session, 'test_client_1')
            assert stored_session.subscriptions == [Subscription(topic='sensors/#', qos=1)]


@pytest.mark.asyncio
async def test_update_stored_session(db_file, broker_context, db_session_factory):
    broker_context.config = SessionDBPlugin.Config(file=db_file)

    # create session for client id (without subscription)
    await broker_context.add_subscription('test_client_1', None, None)

    session, _ = broker_context.get_session('test_client_1')
    assert session is not None
    session.clean_session = True

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

    await session_db_plugin.on_broker_client_subscribed(client_id='test_client_1', topic='my/topic', qos=2)

    has_stored_session = False
    async with aiosqlite.connect(str(db_file)) as db:
        async with await db.execute("SELECT * FROM stored_sessions") as cursor:
            async for row in cursor:
                assert row[1] == 'test_client_1'
                assert row[-1] == '[{"topic": "sensors/#", "qos": 1}, {"topic": "my/topic", "qos": 2}]'
                has_stored_session = True
    assert has_stored_session


# @pytest.mark.asyncio
# async def test_create_stored_session() -> None:
#
#     cfg = {
#         'listeners': {
#             'default': {
#                 'type': 'tcp',
#                 'bind': '127.0.0.1:1883'
#             }
#         },
#         'plugins': {
#             'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow-anonymous': True},
#             'amqtt.plugins.persistence.SessionDBPlugin': {}
#         }
#     }
#
#     b = Broker(config=cfg)
#     await b.start()
#     await asyncio.sleep(1)
#
#     c = MQTTClient(client_id='test_client1', config={'auto_reconnect':False})
#     await c.connect(cleansession=False)
#     await c.subscribe(
#         [
#             ('my/topic', QOS_0)
#         ]
#     )
#
#     await c.disconnect()
#     await asyncio.sleep(2)
#     await b.shutdown()
#     await asyncio.sleep(1)








"""

def test_create_tables(self) -> None:
    dbfile = Path(__file__).resolve().parent / "test.db"

    context = BaseContext()
    context.logger = logging.getLogger(__name__)
    context.config = {"persistence": {"file": str(dbfile)}}  # Ensure string path for config
    SQLitePlugin(context)

    try:
        conn = sqlite3.connect(str(dbfile))  # Convert Path to string for sqlite connection
        cursor = conn.cursor()
        rows = cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = [row[0] for row in rows]  # List comprehension for brevity
        assert "session" in tables
    finally:
        conn.close()

def test_save_session(self) -> None:
    dbfile = Path(__file__).resolve().parent / "test.db"

    context = BaseContext()
    context.logger = logging.getLogger(__name__)
    context.config = {"persistence": {"file": str(dbfile)}}  # Ensure string path for config
    sql_plugin = SQLitePlugin(context)

    s = Session()
    s.client_id = "test_save_session"

    self.loop.run_until_complete(sql_plugin.save_session(session=s))

    try:
        conn = sqlite3.connect(str(dbfile))  # Convert Path to string for sqlite connection
        cursor = conn.cursor()
        row = cursor.execute("SELECT client_id FROM session WHERE client_id = 'test_save_session'").fetchone()
        assert row is not None
        assert row[0] == s.client_id
    finally:
        conn.close()
"""