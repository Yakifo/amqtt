import logging

from dataclasses import dataclass

from amqtt.broker import Action

from amqtt.plugins.base import BasePlugin, BaseAuthPlugin, BaseTopicPlugin
from amqtt.plugins.contexts import BaseContext

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


class AuthPlugin(BaseAuthPlugin):

    async def authenticate(self, *, session: Session) -> bool | None:
        return True


class NoAuthPlugin(BaseAuthPlugin):


    async def authenticate(self, *, session: Session) -> bool | None:
        return False


class TestTopicPlugin(BaseTopicPlugin):

    def __init__(self, context: BaseContext):
        super().__init__(context)

    def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool:
        return True
