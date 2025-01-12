from typing import Any

from amqtt.broker import Action
from amqtt.plugins.manager import BaseContext


class BaseTopicPlugin:
    def __init__(self, context: BaseContext) -> None:
        self.context = context
        self.topic_config: dict[str, Any] | None = self.context.config.get("topic-check", None) if self.context.config else None
        if self.topic_config is None:
            self.context.logger.warning("'topic-check' section not found in context configuration")

    async def topic_filtering(self, *args: Any, **kwargs: Any) -> bool:
        if not self.topic_config:
            # auth config section not found
            self.context.logger.warning("'auth' section not found in context configuration")
            return False
        return True


class TopicTabooPlugin(BaseTopicPlugin):
    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)
        self._taboo: list[str] = ["prohibited", "top-secret", "data/classified"]

    async def topic_filtering(self, *args: Any, **kwargs: Any) -> bool:
        filter_result = await super().topic_filtering(*args, **kwargs)
        if filter_result:
            session = kwargs.get("session")
            topic = kwargs.get("topic")
            if session and session.username == "admin":
                return True
            return not (topic and topic in self._taboo)
        return filter_result


class TopicAccessControlListPlugin(BaseTopicPlugin):
    # def __init__(self, context: BaseContext) -> None:
    #     super().__init__(context)

    @staticmethod
    def topic_ac(topic_requested: str, topic_allowed: str) -> bool:
        req_split = topic_requested.split("/")
        allowed_split = topic_allowed.split("/")
        ret = True
        for i in range(max(len(req_split), len(allowed_split))):
            try:
                a_aux = req_split[i]
                b_aux = allowed_split[i]
            except IndexError:
                ret = False
                break
            if b_aux == "#":
                break
            if b_aux in ("+", a_aux):
                continue
            ret = False
            break
        return ret

    async def topic_filtering(self, *args: Any, **kwargs: Any) -> bool:
        filter_result = await super().topic_filtering(*args, **kwargs)
        if not filter_result:
            return False

        # hbmqtt and older amqtt do not support publish filtering
        action = kwargs.get("action")
        if action == Action.PUBLISH and self.topic_config is not None and "publish-acl" not in self.topic_config:
            # maintain backward compatibility, assume permitted
            return True

        req_topic = kwargs.get("topic")
        if not req_topic:
            return False

        session = kwargs.get("session")
        username = session.username if session else None
        if username is None:
            username = "anonymous"

        acl: dict[str, Any] = {}
        if self.topic_config is not None and action == Action.PUBLISH:
            acl = self.topic_config.get("publish-acl", {})
        elif self.topic_config is not None and action == Action.SUBSCRIBE:
            acl = self.topic_config.get("acl", {})

        allowed_topics = acl.get(username, None)
        if not allowed_topics:
            return False

        return any(self.topic_ac(req_topic, allowed_topic) for allowed_topic in allowed_topics)
