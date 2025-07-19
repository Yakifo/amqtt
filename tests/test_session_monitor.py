import asyncio
import logging

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.contexts import BrokerConfig, ListenerConfig, ConnectionConfig, ClientConfig

logger = logging.getLogger(__name__)

@pytest.fixture
def session_broker_config():
     return BrokerConfig(
        listeners={
            'default': ListenerConfig(bind='127.0.0.1:1883')
        },
        session_expiry_interval=2,
        plugins={
            'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': False}
        })


@pytest.mark.parametrize("username,clean_session,expiration,session_count",
                         [
                             # session expiration disabled
                             ("", True, None, 0),  # anonymous and clean session
                             ("", False, None, 0), # anonymous
                             ("myuser@", True, None, 0), # named user, clean session
                             ("myuser@", False, None, 1), # named user

                             # session expiration enabled
                             ("myuser@", False, 1, 0), # named user, quick expiration
                             ("myuser@", False, 20, 1), # named user, long expiration
                         ])
@pytest.mark.asyncio
async def test_clear_session_expiration(caplog, session_broker_config, username, clean_session, session_count, expiration):
    caplog.set_level(logging.DEBUG)

    session_broker_config.session_expiry_interval = expiration
    session_broker_config.plugins = {'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': username == ""}}

    broker = Broker(config=session_broker_config)
    await broker.start()
    await asyncio.sleep(0.1)
    assert len(broker._sessions) < 1

    c = MQTTClient(config=ClientConfig(cleansession=clean_session, auto_reconnect=False))
    await c.connect(f'mqtt://{username}127.0.0.1:1883')
    await asyncio.sleep(0.1)
    assert len(broker._sessions) == 1
    await asyncio.sleep(0.1)
    await c.disconnect()
    await asyncio.sleep(2)
    assert len(broker._sessions) == session_count

    if not session_count:
        assert any([record for record in caplog.records if "Expired 1 sessions" in record.message]) == (session_count == 0)

    await broker.shutdown()
