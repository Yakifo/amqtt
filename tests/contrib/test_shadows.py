import sqlite3
import tempfile
from pathlib import Path

import aiosqlite
import pytest
from requests import session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from amqtt.broker import BrokerContext, Broker
from amqtt.contrib.shadows import ShadowPlugin
from amqtt.contrib.shadows.models import Shadow, ShadowUpdateError
from amqtt.contrib.shadows.states import StateDocument, State


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
async def db_session_maker(db_connection):
    engine = create_async_engine(f"{db_connection}")
    db_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    yield db_session_maker


@pytest.fixture
@pytest.mark.asyncio
async def shadow_plugin(db_connection):

    cfg = ShadowPlugin.Config(connection=db_connection)
    ctx = BrokerContext(broker=Broker())
    ctx.config = cfg

    shadow_plugin = ShadowPlugin(ctx)
    await shadow_plugin.on_broker_pre_start()
    yield shadow_plugin


@pytest.mark.asyncio
async def test_shadow_find_latest_empty(db_session_maker, shadow_plugin):
    async with db_session_maker() as db_session, db_session.begin():
        shadow = await Shadow.latest_version(session=db_session, device_id='device123', name="myShadowName")
        assert shadow is None


@pytest.mark.asyncio
async def test_shadow_create_new(db_file, db_connection, db_session_maker, shadow_plugin):
    async with db_session_maker() as db_session, db_session.begin():
        shadow = Shadow(device_id='device123', name="myShadowName")
        db_session.add(shadow)
        await db_session.commit()

    async with aiosqlite.connect(db_file) as db_conn:
        db_conn.row_factory = sqlite3.Row  # Set the row_factory

        has_shadow = False
        async with await db_conn.execute("SELECT * FROM shadows_shadow") as cursor:
            for row in await cursor.fetchall():
                assert row['name'] == 'myShadowName'
                assert row['device_id'] == 'device123'
                assert row['state'] == '{}'
                has_shadow = True

        assert has_shadow, "Shadow was not created."

@pytest.mark.asyncio
async def test_shadow_create_find_empty_state(db_connection, db_session_maker, shadow_plugin):
    async with db_session_maker() as db_session, db_session.begin():
        shadow = Shadow(device_id='device123', name="myShadowName")
        db_session.add(shadow)
        await db_session.commit()
        await db_session.flush()

    async with db_session_maker() as db_session, db_session.begin():
        shadow = await Shadow.latest_version(session=db_session, device_id='device123', name="myShadowName")
        assert shadow is not None
        assert shadow.version == 1
        assert shadow.state == StateDocument()


@pytest.mark.asyncio
async def test_shadow_create_find_state_doc(db_connection, db_session_maker, shadow_plugin):
    state_doc = StateDocument(
            state=State(
                desired={'item1': 'value1', 'item2': 'value2'},
                reported={'item3': 'value3', 'item4': 'value4'},
            )
        )
    async with db_session_maker() as db_session, db_session.begin():
        shadow = Shadow(device_id='device123', name="myShadowName")
        shadow.state = state_doc
        db_session.add(shadow)
        await db_session.commit()
        await db_session.flush()

    async with db_session_maker() as db_session, db_session.begin():
        shadow = await Shadow.latest_version(session=db_session, device_id='device123', name="myShadowName")
        assert shadow is not None
        assert shadow.version == 1
        assert shadow.state == state_doc

@pytest.mark.asyncio
async def test_shadow_update_state(db_connection, db_session_maker, shadow_plugin):
    state_doc = StateDocument(
            state=State(
                desired={'item1': 'value1', 'item2': 'value2'},
                reported={'item3': 'value3', 'item4': 'value4'},
            )
        )
    async with db_session_maker() as db_session, db_session.begin():
        shadow = Shadow(device_id='device123', name="myShadowName")
        shadow.state = state_doc
        db_session.add(shadow)
        await db_session.commit()
        await db_session.flush()

    async with db_session_maker() as db_session, db_session.begin():
        shadow = await Shadow.latest_version(session=db_session, device_id='device123', name="myShadowName")
        assert shadow is not None
        shadow.state = StateDocument(
            state=State(
                desired={'item5': 'value5', 'item6': 'value6'},
                reported={'item7': 'value7', 'item8': 'value8'},
            )
        )
        with pytest.raises(ShadowUpdateError):
            await db_session.commit()


@pytest.mark.asyncio
async def test_shadow_update_state(db_connection, db_session_maker, shadow_plugin):
    state_doc = StateDocument(
        state=State(
            desired={'item1': 'value1', 'item2': 'value2'},
            reported={'item3': 'value3', 'item4': 'value4'},
        )
    )
    async with db_session_maker() as db_session, db_session.begin():
        shadow = Shadow(device_id='device123', name="myShadowName")
        shadow.state = state_doc
        db_session.add(shadow)
        await db_session.commit()

    async with db_session_maker() as db_session, db_session.begin():
        shadow = await Shadow.latest_version(session=db_session, device_id='device123', name="myShadowName")
        assert shadow is not None
        shadow.state += StateDocument(
            state=State(
                desired={'item1': 'value1a', 'item6': 'value6'}
            )
        )
        await db_session.commit()

    async with db_session_maker() as db_session, db_session.begin():
        shadow_list = await Shadow.all(db_session, "device123", "myShadowName")
        assert len(shadow_list) == 2

    async with db_session_maker() as db_session, db_session.begin():
        shadow = await Shadow.latest_version(session=db_session, device_id='device123', name="myShadowName")
        assert shadow is not None
        assert shadow.version == 2
        assert shadow.state.state.desired == {'item1': 'value1a', 'item2': 'value2', 'item6': 'value6'}
        assert shadow.state.state.reported == {'item3': 'value3', 'item4': 'value4'}
