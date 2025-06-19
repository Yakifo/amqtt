from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any

from aiohttp import ClientResponse, ClientSession

from amqtt.broker import Action, BrokerContext
from amqtt.plugins.authentication import BaseAuthPlugin
from amqtt.plugins.topic_checking import BaseTopicPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


class ResponseMode(StrEnum):
    STATUS = "status"
    JSON = "json"
    TEXT = "text"

class RequestMethod(StrEnum):
    GET = "get"
    POST = "post"
    PUT = "put"


class ParamsMode(StrEnum):
    JSON = "json"
    FORM = "form"


class ACLError(Exception):
    pass


HTTP_2xx_MIN = 200
HTTP_2xx_MAX = 300


class HttpACL(BaseAuthPlugin, BaseTopicPlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self.http = ClientSession()

        match self.context.config.request_method:
            case RequestMethod.GET:
                self.method = self.http.get
            case RequestMethod.PUT:
                self.method = self.http.put
            case _:
                self.method = self.http.post

    @staticmethod
    def _is_2xx(r: ClientResponse) -> bool:
        return HTTP_2xx_MIN <= r.status < HTTP_2xx_MAX

    async def _send_request(self, url: str, payload: dict[str, Any]) -> bool:

        match self.context.config.params_mode:
            case ParamsMode.FORM:
                kwargs = { "params": payload}
            case _:
                kwargs = { "json": payload}

        async with self.method(url, **kwargs) as r:
            if not self._is_2xx(r):
                return False

            match self.context.config.response_mode:

                case ResponseMode.TEXT:
                    raise NotImplementedError
                case ResponseMode.STATUS:
                    return self._is_2xx(r)
                case _:
                    data = await r.json()
                    if "Ok" not in data:
                        logger.debug('acl response is missing "Ok" field')
                        return False
                    if isinstance(data["Ok"], bool):
                        return data["Ok"]
            return False


    async def authenticate(self, *, session: Session) -> bool | None:
        # async with self.method() as response:

        return False

    async def topic_filtering(self, *,
                        session: Session | None = None,
                        topic: str | None = None,
                        action: Action | None = None) -> bool:
        return False

    @dataclass
    class Config:
        host: str
        port: int
        get_user_uri: str
        acl_uri: str
        request_method: RequestMethod = RequestMethod.GET
        params_mode: ParamsMode = ParamsMode.JSON
        get_superuser_uri: str | None = None
        with_tls: bool = False
        response_mode: ResponseMode = ResponseMode.JSON
        timeout: int = 5
        user_agent: str = "amqtt"
