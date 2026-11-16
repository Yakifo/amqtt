
"""Rate-limiting algorithms for MQTT publications."""

from dataclasses import dataclass
import time


class RateLimiter:
    """Provide a base class for rate limiters."""

    def __init__(self, message_limit: int, time_window: float) -> None:
        self.message_limit = message_limit
        self.time_window = time_window

    def allow(self, client_id: str) -> bool:
        """Determine whether a client may send a message."""
        raise NotImplementedError


@dataclass
class Bucket:
    """Store the current token count and last update time."""

    tokens: float
    last_updated: float


class TokenBucketRateLimiter(RateLimiter):
    """Limit publications using a token bucket."""

    def __init__(
        self,
        message_limit: int,
        time_window: float,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(message_limit, time_window)

        self.max_tokens = (
            max_tokens if max_tokens is not None else message_limit
        )

        if message_limit <= 0 or time_window <= 0:
            raise ValueError

        if self.max_tokens <= 0:
            raise ValueError

        self.refill_rate = message_limit / time_window
        self.buckets: dict[str, Bucket] = {}

    def allow(self, client_id: str) -> bool:
        now = time.monotonic()

        if client_id not in self.buckets:
            self.buckets[client_id] = Bucket(
                tokens=float(self.max_tokens),
                last_updated=now,
            )

        bucket = self.buckets[client_id]
        elapsed = now - bucket.last_updated

        bucket.tokens = min(
            self.max_tokens,
            bucket.tokens + elapsed * self.refill_rate,
        )
        bucket.last_updated = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True

        return False


class WindowRateLimiter(RateLimiter):
    """Limit publications using a sliding time window."""

    def __init__(self, message_limit: int, time_window: float) -> None:
        super().__init__(message_limit, time_window)

        if message_limit <= 0 or time_window <= 0:
            raise ValueError

        self.timestamps: dict[str, list[float]] = {}

    def allow(self, client_id: str) -> bool:
        now = time.monotonic()

        if client_id not in self.timestamps:
            self.timestamps[client_id] = []

        client_timestamps = self.timestamps[client_id]

        while (
            client_timestamps
            and now - client_timestamps[0] >= self.time_window
        ):
            client_timestamps.pop(0)

        if len(client_timestamps) >= self.message_limit:
            return False

        client_timestamps.append(now)
        return True
