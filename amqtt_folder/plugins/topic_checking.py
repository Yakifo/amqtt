from ..broker import Action


class BaseTopicPlugin:
    def __init__(self, context):
        self.context = context
        try:
            self.topic_config = self.context.config["topic-check"]
        except KeyError:
            self.context.logger.warning(
                "'topic-check' section not found in context configuration"
            )
            self.topic_config = None

    def topic_filtering(self, *args, **kwargs):
        if not self.topic_config:
            # auth config section not found
            self.context.logger.warning(
                "'topic-check' section not found in context configuration"
            )
            return False
        return True


class TopicTabooPlugin(BaseTopicPlugin):
    def __init__(self, context):
        super().__init__(context)
        self._taboo = ["prohibited", "top-secret", "data/classified"]

    async def topic_filtering(self, *args, **kwargs):
        filter_result = super().topic_filtering(*args, **kwargs)
        if filter_result:
            session = kwargs.get("session", None)
            topic = kwargs.get("topic", None)
            if session.username and session.username == "admin":
                return True
            if topic and topic in self._taboo:
                return False
            return True
        return filter_result


class TopicAccessControlListPlugin(BaseTopicPlugin):
    def __init__(self, context):
        super().__init__(context)

    @staticmethod
    def topic_ac(topic_requested, topic_allowed):
        #Burcu: Örnek = topic_allowed = a/# . topic_requested = a/b/c  -> ret = True
        req_split = topic_requested.split("/")    #Burcu: req_split = ["a", "b", "c"]
        allowed_split = topic_allowed.split("/")  #Burcu: req_split = ["a", "#"]
        ret = True
        for i in range(max(len(req_split), len(allowed_split))): #Burcu: range(3)
            try:
                a_aux = req_split[i]
                b_aux = allowed_split[i]
            except IndexError:
                ret = False
                break
            if b_aux == "#":
                break
            elif (b_aux == "+") or (b_aux == a_aux):
                continue
            else:
                ret = False
                break
        return ret

    async def topic_filtering(self, *args, **kwargs):
        filter_result = super().topic_filtering(*args, **kwargs)
        if not filter_result:
            return False     #Burcu: ğer config dosyasında topic_check tanımı yoksa False return ediyor = izin yok

        # hbmqtt and older amqtt do not support publish filtering
        action = kwargs.get("action", None)
        if action == Action.publish and "publish-acl" not in self.topic_config:
            # maintain backward compatibility, assume permitted
            return True          #Burcu: Eğer action publish ise ve configin topic_check'inde publish-acl yoksa, izin olmadan her user published edebilir.

        req_topic = kwargs.get("topic", None)
        if not req_topic:
            return False      #Burcu: Topic adı boşsa False

        session = kwargs.get("session", None)
        username = session.username
        if username is None:
            username = "anonymous"

        if action == Action.publish:
            acl = self.topic_config["publish-acl"]   
        elif action == Action.subscribe:
            acl = self.topic_config["acl"]

        allowed_topics = acl.get(username, None)   #Burcu: Acl tanımlarındaki username kısmında session'ın usernameini içeren topicleri get ediyor.
        if not allowed_topics:
            return False

        for allowed_topic in allowed_topics:   
            if self.topic_ac(req_topic, allowed_topic):   #Burcu: publish ya da subscribe için request edilen topic'in allowed topics içinde olup olmadığını kontrol ediyor
                return True

        return False
