
"""Plugin for limiting MQTT publications per client."""

from dataclasses import dataclass

from amqtt.contexts import Action, BaseContext
from amqtt.plugins.base import BaseTopicPlugin
from amqtt.session import Session

from .limiters import TokenBucketRateLimiter, WindowRateLimiter


class ThrottlePlugin(BaseTopicPlugin):
    """Limit the rate of MQTT publications per client."""

    @dataclass
    class Config:
        """Store the throttle plugin configuration."""

        algorithm: str = "token_bucket"
        message_limit: int = 10
        time_window: int = 4
        max_tokens: int = 20

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        config = self.config

        if config.message_limit <= 0:
            message = "message_limit must be positive"
            raise ValueError(message)

        if config.time_window <= 0:
            message = "time_window must be positive"
            raise ValueError(message)

        if config.max_tokens <= 0:
            message = "max_tokens must be positive"
            raise ValueError(message)

        if config.algorithm not in ("token_bucket", "sliding_window"):
            message = f"Unknown algorithm: {config.algorithm}"
            raise ValueError(message)

        self.allowed_count = 0
        self.denied_count = 0

        if config.algorithm == "token_bucket":
            self.rate_limiter = TokenBucketRateLimiter(
                message_limit=config.message_limit,
                time_window=config.time_window,
                max_tokens=config.max_tokens,
            )
        else:
            self.rate_limiter = WindowRateLimiter(
                message_limit=config.message_limit,
                time_window=config.time_window,
            )

    async def topic_filtering(
        self,
        *,
        session: Session | None = None,
        topic: str | None = None,
        action: Action | None = None,
    ) -> bool:
        """Allow or deny a topic action based on the client's rate limit."""
        if action != Action.PUBLISH:
            return True

        if session is None or session.client_id is None:
            return False

        if self.rate_limiter is None:
            message = "Rate limiter has not been initialized"
            raise RuntimeError(message)

        allowed = self.rate_limiter.allow(session.client_id)

        if allowed:
            self.allowed_count += 1
        else:
            self.denied_count += 1

        return allowed
