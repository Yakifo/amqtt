
from dataclasses import dataclass

from amqtt.contexts import Action, BaseContext
from amqtt.plugins.base import BaseTopicPlugin
from amqtt.session import Session


class ThrottlePlugin(BaseTopicPlugin):
    """Limits the rate of MQTT publications per client."""

    @dataclass
    class Config:
        algorithm: str = "token_bucket"
        message_limit: int = 10
        time_window: int = 4
        max_tokens: int = 20

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        config = self.config

        # Validate configuration
        if config.message_limit <= 0:
            raise ValueError("message_limit must be positive")

        if config.time_window <= 0:
            raise ValueError("time_window must be positive")

        if config.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        if config.algorithm not in ("token_bucket", "sliding_window"):
            raise ValueError(f"Unknown algorithm: {config.algorithm}")

        # Metrics
        self.allowed_count = 0
        self.denied_count = 0

        # TODO: Initialize the selected rate limiter here
        self.rate_limiter = None

    async def topic_filtering(
        self,
        *,
        session: Session | None = None,
        topic: str | None = None,
        action: Action | None = None,
    ) -> bool:

        # Only limit publications
        if action != Action.PUBLISH:
            return True

        # A client session is required
        if session is None or session.client_id is None:
            return False

        # TODO: Connect this to the selected rate limiter
        if self.rate_limiter is None:
            raise RuntimeError("Rate limiter has not been initialized")

        allowed = self.rate_limiter.allow(session.client_id)

        # Update metrics
        if allowed:
            self.allowed_count += 1
        else:
            self.denied_count += 1

        return allowed
