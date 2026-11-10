
import logging

import pytest

from amqtt.contexts import Action, BaseContext
from amqtt.contrib.throttle.plugin import ThrottlePlugin
from amqtt.session import Session


class FakeRateLimiter:
    def __init__(self, result: bool):
        self.result = result
        self.calls = []

    def allow(self, client_id: str) -> bool:
        self.calls.append(client_id)
        return self.result


def make_plugin(result: bool = True):
    context = BaseContext()
    context.logger = logging.getLogger("test")
    context.config = ThrottlePlugin.Config()

    plugin = ThrottlePlugin(context)
    limiter = FakeRateLimiter(result)
    plugin.rate_limiter = limiter

    return plugin, limiter


@pytest.mark.asyncio
async def test_non_publish_action_does_not_use_limiter():
    plugin, limiter = make_plugin()
    session = Session()
    session.client_id = "client-1"

    result = await plugin.topic_filtering(
        action=Action.SUBSCRIBE,
        session=session,
        topic="test/topic",
    )

    assert result is True
    assert limiter.calls == []
    assert plugin.allowed_count == 0
    assert plugin.denied_count == 0


@pytest.mark.asyncio
async def test_allowed_publish():
    plugin, limiter = make_plugin(result=True)
    session = Session()
    session.client_id = "client-1"

    result = await plugin.topic_filtering(
        action=Action.PUBLISH,
        session=session,
        topic="test/topic",
    )

    assert result is True
    assert limiter.calls == ["client-1"]
    assert plugin.allowed_count == 1
    assert plugin.denied_count == 0


@pytest.mark.asyncio
async def test_denied_publish():
    plugin, limiter = make_plugin(result=False)
    session = Session()
    session.client_id = "client-1"

    result = await plugin.topic_filtering(
        action=Action.PUBLISH,
        session=session,
        topic="test/topic",
    )

    assert result is False
    assert limiter.calls == ["client-1"]
    assert plugin.allowed_count == 0
    assert plugin.denied_count == 1


@pytest.mark.asyncio
async def test_missing_session_denies_publish():
    plugin, limiter = make_plugin()

    result = await plugin.topic_filtering(
        action=Action.PUBLISH,
        session=None,
        topic="test/topic",
    )

    assert result is False
    assert limiter.calls == []
    assert plugin.allowed_count == 0
    assert plugin.denied_count == 0


@pytest.mark.asyncio
async def test_missing_client_id_denies_publish():
    plugin, limiter = make_plugin()
    session = Session()

    result = await plugin.topic_filtering(
        action=Action.PUBLISH,
        session=session,
        topic="test/topic",
    )

    assert result is False
    assert limiter.calls == []

