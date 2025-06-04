from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aiohttp import ClientResponse, ClientSession
from dacite import from_dict

from amqtt.broker import Action, BrokerContext
from amqtt.plugins.authentication import BaseAuthPlugin
from amqtt.plugins.topic_checking import BaseTopicPlugin
from amqtt.session import Session


class ResponseMode(StrEnum):
    STATUS = "status"
    JSON = "json"
    TEXT = "text"

class ResponseMethod(StrEnum):
    GET = "get"
    POST = "post"
    PUT = "put"

@dataclass
class HttpACLConfig:

    get_user_uri: str
    get_acl_uri: str
    get_superuser_uri: str | None = None
    with_tls: bool = False
    response_mode: ResponseMode = ResponseMode.JSON
    response_method: ResponseMethod = ResponseMethod.GET
    timeout: int = 5


class ACLError(Exception):
    pass


HTTP_2xx_MIN = 200
HTTP_2xx_MAX = 300


class HttpACL(BaseAuthPlugin, BaseTopicPlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self.http = ClientSession()
        self.config = self._get_config()

        match self.config.response_method:
            case ResponseMethod.GET:
                self.method = self.http.get
            case ResponseMethod.PUT:
                self.method = self.http.put
            case _:
                self.method = self.http.post


    def _get_config(self, name: str = "") -> HttpACLConfig:
        config: dict[str, Any] = self._get_config_section("http") or {}
        return from_dict(data_class=HttpACLConfig, data=config)

    @staticmethod
    def _is_2xx(r: ClientResponse) -> bool:
        return HTTP_2xx_MIN <= r.status < HTTP_2xx_MAX

    async def _send_request(self, url: str) -> bool:
        async with self.method(url) as r:
            if not self._is_2xx(r):
                return False

            match self.config.response_mode:

                case ResponseMode.TEXT:
                    pass
                case ResponseMode.STATUS:
                    return self._is_2xx(r)
                case _:
                    data = await r.json()
                    if "Ok" not in data or "Error" not in data:
                        msg = 'response is missing "Ok" or "Error"'
                        raise ACLError(msg)
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
