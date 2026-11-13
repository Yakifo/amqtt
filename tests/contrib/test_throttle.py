
import logging

import pytest

from amqtt.contexts import Action, BaseContext
from amqtt.contrib.throttle.plugin import ThrottlePlugin
from amqtt.session import Session
from amqtt.contrib.throttle.limiters import (
    TokenBucketRateLimiter,
    WindowRateLimiter,
)


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

def test_token_bucket_enforces_max_tokens():
    limiter = TokenBucketRateLimiter(
        message_limit=2,
        time_window=4,
        max_tokens=2,
    )

    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False


def test_token_bucket_refills_tokens(monkeypatch):
    current_time = [100.0]
    monkeypatch.setattr(
        "amqtt.contrib.throttle.limiters.time.monotonic",
        lambda: current_time[0],
    )

    limiter = TokenBucketRateLimiter(
        message_limit=2,
        time_window=4,
        max_tokens=2,
    )

    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False

    current_time[0] += 2

    assert limiter.allow("client-1") is True


def test_token_bucket_tracks_clients_separately():
    limiter = TokenBucketRateLimiter(
        message_limit=1,
        time_window=4,
        max_tokens=1,
    )

    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False

    assert limiter.allow("client-2") is True

def test_window_limiter_enforces_message_limit():
    limiter = WindowRateLimiter(message_limit=2, time_window=10)

    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False


def test_window_limiter_tracks_clients_separately():
    limiter = WindowRateLimiter(message_limit=1, time_window=10)

    assert limiter.allow("client-1") is True
    assert limiter.allow("client-1") is False
    assert limiter.allow("client-2") is True


def test_window_limiter_allows_messages_after_window_expires():
    from unittest.mock import patch

    limiter = WindowRateLimiter(message_limit=1, time_window=10)

    with patch(
        "amqtt.contrib.throttle.limiters.time.monotonic",
        side_effect=[0, 10],
    ):
        assert limiter.allow("client-1") is True
        assert limiter.allow("client-1") is True
def test_plugin_selects_token_bucket_by_default():
    context = BaseContext()
    context.logger = logging.getLogger("test")
    context.config = ThrottlePlugin.Config()

    plugin = ThrottlePlugin(context)

    assert isinstance(plugin.rate_limiter, TokenBucketRateLimiter)


def test_plugin_selects_sliding_window_when_configured():
    context = BaseContext()
    context.logger = logging.getLogger("test")
    context.config = ThrottlePlugin.Config(algorithm="sliding_window")

    plugin = ThrottlePlugin(context)

    assert isinstance(plugin.rate_limiter, WindowRateLimiter)
@pytest.mark.parametrize(
    "config",
    [
        {"message_limit": 0},
        {"time_window": 0},
        {"max_tokens": 0},
        {"algorithm": "unknown"},
    ],
)
def test_plugin_rejects_invalid_configuration(config):
    context = BaseContext()
    context.logger = logging.getLogger("test")
    context.config = ThrottlePlugin.Config(**config)

    with pytest.raises(ValueError):
        ThrottlePlugin(context)
def test_window_limiter_slides_over_time(monkeypatch):
    current_time = [0.0]
    monkeypatch.setattr(
        "amqtt.contrib.throttle.limiters.time.monotonic",
        lambda: current_time[0],
    )

    limiter = WindowRateLimiter(message_limit=2, time_window=10)

    assert limiter.allow("client-1") is True  # t=0
    current_time[0] = 5
    assert limiter.allow("client-1") is True  # t=5
    current_time[0] = 10
    assert limiter.allow("client-1") is True  # t=0 has expired
    assert limiter.allow("client-1") is False