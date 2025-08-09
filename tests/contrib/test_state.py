import asyncio
import math

import pytest
import time
from hamcrest import equal_to, assert_that, close_to, has_key, instance_of, has_entry



from amqtt.contrib.shadows import ShadowPlugin, ShadowOperation
from amqtt.contrib.shadows.states import State, StateDocument, calculate_delta_update, calculate_iota_update, \
    MetaTimestamp


@pytest.mark.parametrize("topic,client_id,shadow_name,message_type,is_match", [
    ('$shadow/myclientid/myshadow/get', 'myclientid', 'myshadow', ShadowOperation.GET, True),
    ('$shadow/myshadow/get', '', '', '', False)
])
def test_shadow_topic_match(topic, client_id, shadow_name, message_type, is_match):

    # broker_context = BrokerContext(broker=Broker())
    # shadow_plugin = ShadowPlugin(context=broker_context)
    shadow_topic = ShadowPlugin.shadow_topic_match(topic)
    if is_match:
        assert shadow_topic.device_id == client_id
        assert shadow_topic.name == shadow_name
        assert shadow_topic.message_op in ShadowOperation
        assert shadow_topic.message_op == message_type
    else:
        assert shadow_topic is None


@pytest.mark.asyncio
async def test_state_add():

    cur_time = math.floor(time.time())

    data = {
         'state':{
             'desired': {
                 'item1': 'value1a',
                 'item2': 'value2a'
             },
             'reported': {
                 'item1': 'value1a',
                 'item2': 'value2b'
             }
         }
    }

    meta = {
        'metadata': {
            'desired': {
                'item1': 10,
                'item2': 20
            },
            'reported': {
                'item1': 11,
                'item2': 21
            }
        }
    }

    data_state = State.from_dict(data['state'])
    meta_state = State.from_dict(meta['metadata'])

    state_document_one = StateDocument(state=data_state, metadata=meta_state)
    await asyncio.sleep(2)

    data_update = {
         'state':{
             'desired': {
                 'item2': 'value2a'
             },
             'reported': {
                 'item1': 'value1c',
                 'item2': 'value2c'
             }
         }
    }

    state_document_two = StateDocument.from_dict(data_update)

    final_doc = state_document_one + state_document_two

    assert final_doc.state.desired['item1'] == 'value1a'
    assert final_doc.metadata.desired['item1'] == 10

    assert final_doc.state.desired['item2'] == 'value2a'
    assert final_doc.metadata.desired['item2'] > cur_time

    assert final_doc.state.reported['item1'] == 'value1c'
    assert final_doc.metadata.reported['item1'] > cur_time
    assert final_doc.state.reported['item1'] == 'value1c'
    assert final_doc.metadata.reported['item1'] > cur_time


def test_state_from_dict() -> None:

    state_dict = {
        'desired': {'keyA': 'valueA', 'keyB': 'valueB'},
        'reported': {'keyC': 'valueC', 'keyD': 'valueD'}
    }

    state = State.from_dict(state_dict)

    assert_that(state.desired['keyA'], equal_to('valueA'))
    assert_that(state.desired['keyB'], equal_to('valueB'))
    assert_that(state.reported['keyC'], equal_to('valueC'))
    assert_that(state.reported['keyD'], equal_to('valueD'))


def test_state_doc_from_dict() -> None:
    now = int(time.time())

    state_dict = {
        'state': {
            'desired': {'keyA': 'valueA', 'keyB': 'valueB'},
            'reported': {'keyC': 'valueC', 'keyD': 'valueD'}
        }
    }

    state_doc = StateDocument.from_dict(state_dict)

    assert_that(state_doc.state.desired['keyA'], equal_to('valueA'))
    assert_that(state_doc.state.desired['keyB'], equal_to('valueB'))

    assert_that(state_doc.metadata.desired, has_key('keyA'))  # noqa
    assert_that(state_doc.metadata.desired, has_key('keyB'))  # noqa

    assert_that(state_doc.metadata.desired['keyA'], instance_of(MetaTimestamp))  # noqa
    assert_that(state_doc.metadata.desired['keyB'], instance_of(MetaTimestamp))  # noqa
    assert_that(state_doc.metadata.desired['keyA'], close_to(now, 0))  # noqa
    assert_that(state_doc.metadata.desired['keyA'], equal_to(state_doc.metadata.desired['keyB']))


def test_state_doc_including_meta() -> None:
    now = int(time.time())
    state1 = State(
            desired={'keyA': 'valueA', 'keyB': 'valueB'},
            reported={'keyC': 'valueC', 'keyD': 'valueD'}
        )
    meta1 = State(
        desired={'keyA': now - 100, 'keyB': now - 110},
        reported={'keyC': now - 90, 'keyD': now - 120}
    )

    state_doc1 = StateDocument(
        state=state1,
        metadata=meta1
    )

    state2 = State(
        desired={'keyA': 'valueA', 'keyB': 'valueB'},
        reported={'keyC': 'valueC', 'keyD': 'valueD'}
    )
    meta2 = State(
        desired={'keyA': now - 5, 'keyB': now - 5},
        reported={'keyC': now - 5, 'keyD': now - 5}
    )

    state_doc2 = StateDocument(
        state=state2,
        metadata=meta2
    )

    new_doc = state_doc1 + state_doc2

    assert_that(new_doc.metadata.desired['keyA'], equal_to(now - 5))
    assert_that(new_doc.metadata.reported['keyC'], equal_to(now - 5))


def test_state_doc_plus_new_key_update() -> None:
    now = int(time.time())
    state = State(
            desired={'keyA': 'valueA', 'keyB': 'valueB'},
            reported={'keyC': 'valueC', 'keyD': 'valueD'}
        )
    meta = State(
        desired={'keyA': now - 100, 'keyB': now - 110},
        reported={'keyC': now - 90, 'keyD': now - 120}
    )

    state_doc = StateDocument(
        state=state,
        metadata=meta
    )

    update_dict = {'state': {'reported': {'keyE': 'valueE', 'keyF': 'valueF'}}}
    update = StateDocument.from_dict(update_dict)

    next_doc = state_doc + update

    assert_that(next_doc.state.reported, has_key('keyC'))
    assert_that(next_doc.metadata.reported['keyC'], equal_to(now - 90))
    assert_that(next_doc.metadata.reported['keyD'], equal_to(now - 120))

    assert_that(next_doc.state.reported, has_key('keyE'))
    assert_that(next_doc.state.reported, has_key('keyF'))
    assert_that(next_doc.metadata.reported['keyE'], close_to(now, 1))
    assert_that(next_doc.metadata.reported['keyF'], close_to(now, 1))


def test_state_with_updated_keys() -> None:

    now = int(time.time())
    state = State(
            desired={'keyA': 'valueA', 'keyB': 'valueB'},
            reported={'keyC': 'valueC', 'keyD': 'valueD'}
        )
    meta = State(
        desired={'keyA': now - 100, 'keyB': now - 110},
        reported={'keyC': now - 90, 'keyD': now - 120}
    )

    state_doc = StateDocument(
        state=state,
        metadata=meta
    )

    update_dict = {'state': {'reported': {'keyD': 'valueD'}}}
    update = StateDocument.from_dict(update_dict)

    next_doc = state_doc + update

    assert_that(next_doc.state.reported, has_key('keyC'))
    assert_that(next_doc.state.reported, has_key('keyD'))
    assert_that(next_doc.metadata.reported['keyC'], equal_to(now - 90))
    assert_that(next_doc.metadata.reported['keyD'], close_to(now, 1))


def test_update_with_empty_initial_state() -> None:
    now = int(time.time())

    prev_doc = StateDocument.from_dict({})

    state = State(
            desired={'keyA': 'valueA', 'keyB': 'valueB'},
            reported={'keyC': 'valueC', 'keyD': 'valueD'}
        )

    state_doc = StateDocument(state=state)
    new_doc = prev_doc + state_doc

    assert_that(state_doc.state.desired, equal_to(new_doc.state.desired))
    assert_that(state_doc.state.reported, equal_to(new_doc.state.reported))
    assert_that(state_doc.metadata.reported, has_key('keyC'))
    assert_that(state_doc.metadata.reported['keyC'], close_to(now, 1))


def test_update_with_clearing_key() -> None:
    state = State(
            desired={'keyA': 'valueA', 'keyB': 'valueB'},
            reported={'keyC': 'valueC', 'keyD': 'valueD'}
        )

    state_doc = StateDocument(state=state)

    update_doc = StateDocument.from_dict({'state': {'reported': {'keyC': None}}})

    new_doc = state_doc + update_doc

    assert_that(new_doc.state.reported, has_entry(equal_to('keyC'), equal_to(None)))


def test_empty_desired_state() -> None:

    state_doc = StateDocument.from_dict({
        'state': {
            'reported': {
                'items': ['value1', 'value2', 'value3']
            }
        }
    })

    diff = calculate_delta_update(state_doc.state.desired, state_doc.state.reported)
    assert diff == {}


def test_empty_reported_state() -> None:

    state_doc = StateDocument.from_dict({
        'state': {
            'desired': {
                'items': ['value1', 'value2', 'value3']
            }
        }
    })

    diff = calculate_delta_update(state_doc.state.desired, state_doc.state.reported)
    assert diff == {'items': ['value1', 'value2', 'value3']}


def test_matching_desired_reported_state() -> None:

    state_doc = StateDocument.from_dict({
        'state': {
            'desired': {
                'items': ['value1', 'value2', 'value3']
            },
            'reported': {
                'items': ['value1', 'value2', 'value3']
            }
        }
    })

    diff = calculate_delta_update(state_doc.state.desired, state_doc.state.reported)
    assert diff == {}


def test_out_of_order_list() -> None:

    state_doc = StateDocument.from_dict({
        'state': {
            'desired': {
                'items': ['value1', 'value2', 'value3']
            },
            'reported': {
                'items': ['value2', 'value1', 'value3']
            }
        }
    })

    diff = calculate_delta_update(state_doc.state.desired, state_doc.state.reported)
    assert diff == { 'items': ['value1', 'value2', 'value3'] }

def test_states_with_connector_transaction() -> None:
    state_doc = StateDocument.from_dict({
        'state': {
            'desired': {},
            'reported': {"transaction": False, "transactionId": "5678", "tag": "ghijk"}
        }
    })

    diff = calculate_iota_update(state_doc.state.desired, state_doc.state.reported)
    assert diff == {"transaction": None, "transactionId": None, "tag": None}


def test_extra_reported_into_desired_with_overlap() -> None:
    state_doc = StateDocument.from_dict({
        'state': {
            'desired': {"connectors": [1, 2, 3]},
            'reported': {"status": None, "heartbeat": "2025-02-07T04:16:51.431Z", "connectors": [1, 2, 3],
                "module_version": "2.0.1", "restartTime": "2025-02-07T03:16:51.431Z"}
        }})

    diff = calculate_iota_update(state_doc.state.desired, state_doc.state.reported)
    assert diff == {"status": None, "heartbeat": None, "module_version": None, "restartTime": None}

