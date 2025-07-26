"""INIT."""
import re
from typing import Any, Optional


class TopicMatcher:

    _instance: Optional["TopicMatcher"] = None

    def __init__(self) -> None:
        if not hasattr(self, "_topic_filter_matchers"):
            self._topic_filter_matchers: dict[str, re.Pattern[str]] = {}

    def __new__(cls, *args: list[Any], **kwargs: dict[str, Any]) -> "TopicMatcher":
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def is_topic_allowed(self, topic: str, a_filter: str) -> bool:
        if topic.startswith("$") and (a_filter.startswith(("+", "#"))):
            return False

        if "#" not in a_filter and "+" not in a_filter:
            # if filter doesn't contain wildcard, return exact match
            return a_filter == topic

        # else use regex (re.compile is an expensive operation, store the matcher for future use)
        if a_filter not in self._topic_filter_matchers:
            self._topic_filter_matchers[a_filter] = re.compile(re.escape(a_filter)
                                                               .replace("\\#", "?.*")
                                                               .replace("\\+", "[^/]*")
                                                               .lstrip("?"))
        match_pattern = self._topic_filter_matchers[a_filter]
        return bool(match_pattern.fullmatch(topic))
