import datetime
import secrets

import jwt
import pytest

from amqtt.broker import BrokerContext, Broker
from amqtt.contrib.jwt import UserAuthJwtPlugin
from amqtt.session import Session


@pytest.fixture
def secret_key():
    return secrets.token_urlsafe(32)

@pytest.mark.parametrize("exp_time, outcome", [
    (datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1), True),
    (datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1), False),
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
