"""INIT."""
from typing import Any, Optional, cast
from typing_extensions import Self


class TopicMatcher:
    """Singleton class originally provided to optimize topic matching."""

    _instance: Optional["TopicMatcher"] = None

    def __new__(cls, *args: list[Any], **kwargs: dict[str, Any]) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cast("Self", cls._instance)

    @staticmethod
    def is_topic_allowed(topic: str, a_filter: str) -> bool:
        if topic.startswith("$") and (a_filter.startswith(("+", "#"))):
            return False

        if "#" not in a_filter and "+" not in a_filter:
            # if filter doesn't contain wildcard, return exact match
            return a_filter == topic

        sub_levels = a_filter.split("/")
        pub_levels = topic.split("/")

        for i, level in enumerate(sub_levels):
            if ("+" in level and level != "+") or ("#" in level and level != "#"):
                return False

            if level == "#":
                return i == len(sub_levels) - 1

            if i >= len(pub_levels) or level not in ("+", pub_levels[i]):
                return False

        return len(sub_levels) == len(pub_levels)

    def are_topics_allowed(self, topic: str, many_filters: list[str]) -> bool:

        return any(self.is_topic_allowed(topic, a_filter) for a_filter in many_filters)
