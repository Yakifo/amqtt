import asyncio
import logging
import secrets

try:
    from datetime import UTC, datetime, timedelta
except ImportError:
    from datetime import datetime, timezone, timedelta

    UTC = timezone.utc

import jwt
import pytest

from amqtt.broker import BrokerContext, Broker
from amqtt.client import MQTTClient
from amqtt.contexts import Action, ListenerConfig, BrokerConfig
from amqtt.contrib.jwt import UserAuthJwtPlugin, TopicAuthJwtPlugin
from amqtt.mqtt.constants import QOS_0
from amqtt.session import Session


@pytest.fixture
def secret_key():
    return secrets.token_urlsafe(32)


@pytest.mark.parametrize("exp_time, outcome", [
    (datetime.now(UTC) + timedelta(hours=1), True),
    (datetime.now(UTC) - timedelta(hours=1), False),
])
@pytest.mark.asyncio
async def test_user_jwt_plugin(secret_key, exp_time, outcome):

    payload = {
        "username": "example_user",
        "exp": exp_time
    }

    ctx = BrokerContext(Broker())
    ctx.config = UserAuthJwtPlugin.Config(
        secret_key=secret_key,
        user_claim='username'
    )

    jwt_plugin = UserAuthJwtPlugin(context=ctx)

    s = Session()
    s.username = "example_user"
    s.password = jwt.encode(payload, secret_key, algorithm="HS256")

    assert await jwt_plugin.authenticate(session=s) == outcome, "access should have been granted"


@pytest.mark.asyncio
async def test_topic_jwt_plugin(secret_key):

    payload = {
        "username": "example_user",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "publish_acl": ['my/topic/#', 'my/+/other']
    }

    ctx = BrokerContext(Broker())
    ctx.config = TopicAuthJwtPlugin.Config(
        secret_key=secret_key,
        publish_claim='publish_acl',
        subscribe_claim='subscribe_acl',
        receive_claim='receive_acl'
    )

    jwt_plugin = TopicAuthJwtPlugin(context=ctx)

    s = Session()
    s.username = "example_user"
    s.password = jwt.encode(payload, secret_key, algorithm="HS256")

    assert await jwt_plugin.topic_filtering(session=s, topic="my/topic/one", action=Action.PUBLISH), "access should be granted"


@pytest.mark.asyncio
async def test_broker_with_jwt_plugin(secret_key, caplog):
    payload = {
        "username": "example_user",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "publish_acl": ['my/topic/#', 'my/+/other'],
        "subscribe_acl": ['my/+/other'],
    }
    username = "example_user"
    password = jwt.encode(payload, secret_key, algorithm="HS256")

    cfg = BrokerConfig(
        listeners={'default': ListenerConfig()},
        plugins={
            'amqtt.contrib.jwt.UserAuthJwtPlugin': {
                'secret_key': secret_key,
                'user_claim': 'username',
            },
            'amqtt.contrib.jwt.TopicAuthJwtPlugin': {
                'secret_key': secret_key,
                'publish_claim': 'publish_acl',
                'subscribe_claim': 'subscribe_acl',
                'receive_claim': 'receive_acl'
            }
        }
    )
    with caplog.at_level(logging.INFO):
        b = Broker(config=cfg)
        await b.start()
        await asyncio.sleep(0.1)

        c = MQTTClient()
        await c.connect(f'mqtt://{username}:{password}@localhost:1883')
        await asyncio.sleep(0.1)
        result = await c.subscribe([('my/one', QOS_0)])
        assert result == [128, ]
        result = await c.subscribe([('my/one/other', QOS_0)])
        assert result == [0]
        await c.publish('my/one', b'message should not get published')
        await asyncio.sleep(0.1)
        assert "not allowed to publish to TOPIC my/one" in caplog.text
        await asyncio.sleep(0.1)

        await c.disconnect()
        await asyncio.sleep(0.1)
        await b.shutdown()
