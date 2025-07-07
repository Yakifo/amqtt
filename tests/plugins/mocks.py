import logging

from dataclasses import dataclass

from amqtt.plugins.base import BasePlugin, BaseAuthPlugin, BaseTopicPlugin
from amqtt.contexts import BaseContext, Action

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
        option3: int = 20


class TestCoroErrorPlugin(BaseAuthPlugin):

    def authenticate(self, *, session: Session) -> bool | None:
        return True


class TestAuthPlugin(BaseAuthPlugin):

    async def authenticate(self, *, session: Session) -> bool | None:
        return True


class TestNoAuthPlugin(BaseAuthPlugin):


    async def authenticate(self, *, session: Session) -> bool | None:
        return False


class TestAllowTopicPlugin(BaseTopicPlugin):

    def __init__(self, context: BaseContext):
        super().__init__(context)

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool:
        return True


class TestBlockTopicPlugin(BaseTopicPlugin):

    def __init__(self, context: BaseContext):
        super().__init__(context)

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool:
        logger.debug("topic filtering plugin is returning false")
        return False
