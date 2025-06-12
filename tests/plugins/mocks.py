import logging
from dataclasses import dataclass

from amqtt.broker import Action
from amqtt.plugins.authentication import BaseAuthPlugin
from amqtt.plugins.base import BasePlugin
from amqtt.plugins.manager import BaseContext
from amqtt.plugins.topic_checking import BaseTopicPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


class TestSimplePlugin(BasePlugin):

    def __init__(self, context: BaseContext):
        super().__init__(context)


class TestConfigPlugin(BasePlugin):

    def __init__(self, context: BaseContext):
        super().__init__(context)

    @dataclass
    class Config:
        option1: int
        option2: str


class TestAuthPlugin(BaseAuthPlugin):

    def __init__(self, context: BaseContext):
        super().__init__(context)

    async def authenticate(self, *, session: Session) -> bool | None:
        return False


class TestTopicPlugin(BaseTopicPlugin):

    def __init__(self, context: BaseContext):
        super().__init__(context)

    def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool:
        return True
