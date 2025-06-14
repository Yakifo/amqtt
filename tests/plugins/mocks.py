import logging

from amqtt.plugins.authentication import BaseAuthPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


class NoAuthPlugin(BaseAuthPlugin):

    async def authenticate(self, *, session: Session) -> bool | None:
        return False

class AuthPlugin(BaseAuthPlugin):

    async def authenticate(self, *, session: Session) -> bool | None:
        return True

