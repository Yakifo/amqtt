import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, call, ANY

import aiosqlite
import pytest
from jsonschema import validate
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from amqtt.broker import BrokerContext, Broker
from amqtt.contrib.shadows import ShadowPlugin
from amqtt.contrib.shadows.models import Shadow, ShadowUpdateError
from amqtt.contrib.shadows.states import StateDocument, State, MetaTimestamp
from amqtt.mqtt.constants import QOS_0
from amqtt.session import IncomingApplicationMessage
from tests.contrib.test_shadows_schema import *


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

    def new_equal(a, b):
        diff = abs(a.timestamp - b.timestamp)
        return diff <= 2

    async with db_session_maker() as db_session, db_session.begin():
        shadow = await Shadow.latest_version(session=db_session, device_id='device123', name="myShadowName")
        assert shadow is not None
        assert shadow.version == 1
        with patch.object(MetaTimestamp, "__eq__", new=new_equal) as mocked_mqtt_publish:
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


@pytest.mark.asyncio
async def test_shadow_plugin_get_rejected(shadow_plugin):
    """test """

    with patch.object(BrokerContext, 'broadcast_message', return_value=None) as mock_method:
        msg = IncomingApplicationMessage(packet_id=1,
                                             topic='$shadow/myClient123/myShadow/get',
                                             qos=QOS_0,
                                             data=json.dumps({}).encode('utf-8'),
                                             retain=False)
        await shadow_plugin.on_broker_message_received(client_id="myClient123", message=msg)

        mock_method.assert_called()
        topic, message = mock_method.call_args[0]
        assert topic == '$shadow/myClient123/myShadow/get/rejected'
        validate(instance=json.loads(message.decode('utf-8')), schema=get_rejected_schema)

@pytest.mark.asyncio
async def test_shadow_plugin_update_accepted(shadow_plugin):
    with patch.object(BrokerContext, 'broadcast_message', return_value=None) as mock_method:

        update_msg = {
            'state': {
                'desired': {
                    'item1': 'value1',
                    'item2': 'value2'
                }
            }
        }

        validate(instance=update_msg, schema=update_schema)


        msg = IncomingApplicationMessage(packet_id=1,
                                         topic='$shadow/myClient123/myShadow/update',
                                         qos=QOS_0,
                                         data=json.dumps(update_msg).encode('utf-8'),
                                         retain=False)
        await shadow_plugin.on_broker_message_received(client_id="myClient123", message=msg)

        accepted_call = call('$shadow/myClient123/myShadow/update/accepted', ANY)
        document_call = call('$shadow/myClient123/myShadow/update/documents', ANY)
        delta_call = call('$shadow/myClient123/myShadow/update/delta', ANY)
        iota_call = call('$shadow/myClient123/myShadow/update/iota', ANY)

        mock_method.assert_has_calls(
            [
                accepted_call,
                document_call,
                delta_call,
                iota_call,
            ],
            any_order=True,
        )

        for actual in mock_method.call_args_list:
            if actual == accepted_call:
                validate(instance=json.loads(actual.args[1].decode('utf-8')), schema=update_accepted_schema)
            elif actual == document_call:
                validate(instance=json.loads(actual.args[1].decode('utf-8')), schema=update_documents_schema)
            elif actual == delta_call:
                validate(instance=json.loads(actual.args[1].decode('utf-8')), schema=delta_schema)
            elif actual == iota_call:
                validate(instance=json.loads(actual.args[1].decode('utf-8')), schema=delta_schema)
            else:
                assert False, "unknown call made to broadcast"


@pytest.mark.asyncio
async def test_shadow_plugin_get_accepted(shadow_plugin):
    with patch.object(BrokerContext, 'broadcast_message', return_value=None) as mock_method:

        update_msg = {
            'state': {
                'desired': {
                    'item1': 'value1',
                    'item2': 'value2'
                }
            }
        }

        update_msg = IncomingApplicationMessage(packet_id=1,
                                         topic='$shadow/myClient123/myShadow/update',
                                         qos=QOS_0,
                                         data=json.dumps(update_msg).encode('utf-8'),
                                         retain=False)
        await shadow_plugin.on_broker_message_received(client_id="myClient123", message=update_msg)

        mock_method.reset_mock()

        get_msg = IncomingApplicationMessage(packet_id=1,
                                         topic='$shadow/myClient123/myShadow/get',
                                         qos=QOS_0,
                                         data=json.dumps({}).encode('utf-8'),
                                         retain=False)
        await shadow_plugin.on_broker_message_received(client_id="myClient123", message=get_msg)

        get_accepted = call('$shadow/myClient123/myShadow/get/accepted', ANY)

        mock_method.assert_has_calls(
            [get_accepted]
        )

        has_msg = False
        for actual in mock_method.call_args_list:
            if actual == get_accepted:
                validate(instance=json.loads(actual.args[1].decode('utf-8')), schema=get_accepted_schema)
                has_msg = True
        assert has_msg, "could not find the broadcast call for get accepted"
