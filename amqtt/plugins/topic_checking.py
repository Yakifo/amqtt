from dataclasses import dataclass, field
from typing import Any
import warnings

from amqtt.contexts import Action, BaseContext
from amqtt.errors import PluginInitError
from amqtt.plugins.base import BaseTopicPlugin
from amqtt.session import Session


class TopicTabooPlugin(BaseTopicPlugin):
    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)
        self._taboo: list[str] = ["prohibited", "top-secret", "data/classified"]

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool | None:
        filter_result = await super().topic_filtering(session=session, topic=topic, action=action)
        if filter_result:
            if session and session.username == "admin":
                return True
            return not (topic and topic in self._taboo)
        return bool(filter_result)


class TopicAccessControlListPlugin(BaseTopicPlugin):

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

        if self._get_config_option("acl", None):
            warnings.warn("The 'acl' option is deprecated, please use 'subscribe-acl' instead.", stacklevel=1)

        if self._get_config_option("acl", None) and self._get_config_option("subscribe-acl", None):
            msg = "'acl' has been replaced with 'subscribe-acl'; only one may be included"
            raise PluginInitError(msg)

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

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool | None:
        filter_result = await super().topic_filtering(session=session, topic=topic, action=action)
        if not filter_result:
            return False

        # hbmqtt and older amqtt do not support publish filtering
        if action == Action.PUBLISH and not self._get_config_option("publish-acl", {}):
            # maintain backward compatibility, assume permitted
            return True

        req_topic = topic
        if not req_topic:
            return False

        username = session.username if session else None
        if username is None:
            username = "anonymous"

        acl: dict[str, Any] | None = None
        match action:
            case Action.PUBLISH:
                acl = self._get_config_option("publish-acl", None)
            case Action.SUBSCRIBE:
                acl = self._get_config_option("subscribe-acl", self._get_config_option("acl", None))
            case Action.RECEIVE:
                acl = self._get_config_option("receive-acl", None)
            case _:
                msg = "Received an invalid action type."
                raise ValueError(msg)

        if acl is None:
            return True

        allowed_topics = acl.get(username, [])
        if not allowed_topics:
            return False

        return any(self.topic_ac(req_topic, allowed_topic) for allowed_topic in allowed_topics)

    @dataclass
    class Config:
        """Mappings of username and list of approved topics."""

        publish_acl: dict[str, list[str]] = field(default_factory=dict)
        acl: dict[str, list[str]] = field(default_factory=dict)
