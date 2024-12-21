from amqtt.broker import Action


class BaseTopicPlugin:
    def __init__(self, context) -> None:
        self.context = context
        try:
            self.topic_config = self.context.config["topic-check"]
        except KeyError:
            self.context.logger.warning(
                "'topic-check' section not found in context configuration",
            )
            self.topic_config = None

    def topic_filtering(self, *args, **kwargs) -> bool:
        if not self.topic_config:
            # auth config section not found
            self.context.logger.warning(
                "'auth' section not found in context configuration",
            )
            return False
        return True


class TopicTabooPlugin(BaseTopicPlugin):
    def __init__(self, context) -> None:
        super().__init__(context)
        self._taboo = ["prohibited", "top-secret", "data/classified"]

    async def topic_filtering(self, *args, **kwargs):
        filter_result = super().topic_filtering(*args, **kwargs)
        if filter_result:
            session = kwargs.get("session")
            topic = kwargs.get("topic")
            if session.username and session.username == "admin":
                return True
            return not (topic and topic in self._taboo)
        return filter_result


class TopicAccessControlListPlugin(BaseTopicPlugin):
    def __init__(self, context) -> None:
        super().__init__(context)

    @staticmethod
    def topic_ac(topic_requested, topic_allowed):
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

    async def topic_filtering(self, *args, **kwargs) -> bool:
        filter_result = super().topic_filtering(*args, **kwargs)
        if not filter_result:
            return False

        # hbmqtt and older amqtt do not support publish filtering
        action = kwargs.get("action")
        if action == Action.PUBLISH and "publish-acl" not in self.topic_config:
            # maintain backward compatibility, assume permitted
            return True

        req_topic = kwargs.get("topic")
        if not req_topic:
            return False

        session = kwargs.get("session")
        username = session.username
        if username is None:
            username = "anonymous"

        if action == Action.PUBLISH:
            acl = self.topic_config["publish-acl"]
        elif action == Action.SUBSCRIBE:
            acl = self.topic_config["acl"]

        allowed_topics = acl.get(username, None)
        if not allowed_topics:
            return False

        return any(self.topic_ac(req_topic, allowed_topic) for allowed_topic in allowed_topics)
