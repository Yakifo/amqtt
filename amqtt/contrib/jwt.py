import logging
from dataclasses import dataclass
from typing import ClassVar

from amqtt.broker import BrokerContext
from amqtt.plugins import TopicMatcher

try:
    from enum import StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass


from amqtt.contexts import Action
from amqtt.plugins.base import BaseAuthPlugin, BaseTopicPlugin
from amqtt.session import Session

import jwt

logger = logging.getLogger(__name__)


class Algorithms(StrEnum):
    ES256 = 'ES256'
    ES256K = 'ES256K'
    ES384 = 'ES384'
    ES512 = 'ES512'
    ES521 = 'ES521'
    EdDSA = 'EdDSA'
    HS256 = 'HS256'
    HS384 = 'HS384'
    HS512 = 'HS512'
    PS256 = 'PS256'
    PS384 = 'PS384'
    PS512 = 'PS512'
    RS256 = 'RS256'
    RS384 = 'RS384'
    RS512 = 'RS512'


class UserAuthJwtPlugin(BaseAuthPlugin):

    async def authenticate(self, *, session: Session) -> bool | None:

        try:
            decoded_payload = jwt.decode(session.password, self.config.secret_key, algorithms=["HS256"])
            return decoded_payload.get(self.config.user_claim, None) == session.username
        except jwt.ExpiredSignatureError:
            logger.debug(f"jwt for '{session.username}' is expired")
            return False
        except jwt.InvalidTokenError:
            logger.debug(f"jwt for '{session.username}' is invalid")
            return False

    @dataclass
    class Config:
        secret_key: str
        """Secret key to decrypt the token."""
        user_claim: str
        """Payload key for user name."""
        algorithm: str = "HS256"
        """Algorithm to use for token encryption: 'ES256', 'ES256K', 'ES384', 'ES512', 'ES521', 'EdDSA', 'HS256',
         'HS384', 'HS512', 'PS256', 'PS384', 'PS512', 'RS256', 'RS384', 'RS512'"""


class TopicAuthJwtPlugin(BaseTopicPlugin):

    _topic_jwt_claims: ClassVar = {
        Action.PUBLISH: 'publish_claim',
        Action.SUBSCRIBE: 'subscribe_claim',
        Action.RECEIVE: 'receive_claim',
    }

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        self.topic_matcher = TopicMatcher()

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool | None:

        if not any([session, topic, action]):
            return None

        try:
            decoded_payload = jwt.decode(session.password, self.config.secret_key, algorithms=["HS256"])
            claim = getattr(self.config, self._topic_jwt_claims[action])
            return any(self.topic_matcher.is_topic_allowed(topic, a_filter) for a_filter in decoded_payload.get(claim, []))
        except jwt.ExpiredSignatureError:
            logger.debug(f"jwt for '{session.username}' is expired")
            return False
        except jwt.InvalidTokenError:
            logger.debug(f"jwt for '{session.username}' is invalid")
            return False

    @dataclass
    class Config:
        secret_key: str
        """Secret key to decrypt the token."""
        publish_claim: str
        """Payload key for contains a list of permissible publish topics."""
        subscribe_claim: str
        """Payload key for contains a list of permissible subscribe topics."""
        receive_claim: str
        """Payload key for contains a list of permissible receive topics."""
        algorithm: str = "HS256"
        """Algorithm to use for token encryption: 'ES256', 'ES256K', 'ES384', 'ES512', 'ES521', 'EdDSA', 'HS256',
         'HS384', 'HS512', 'PS256', 'PS384', 'PS512', 'RS256', 'RS384', 'RS512'"""
