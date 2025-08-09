from dataclasses import dataclass

try:
    from enum import StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass

import logging
from typing import Any

from aiohttp import ClientResponse, ClientSession, FormData

from amqtt.broker import BrokerContext
from amqtt.contexts import Action
from amqtt.plugins.base import BaseAuthPlugin, BasePlugin, BaseTopicPlugin
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
HTTP_2xx_MAX = 299

HTTP_4xx_MIN = 400
HTTP_4xx_MAX = 499


@dataclass
class HttpConfig:
    """Configuration for the HTTP Auth & ACL Plugin."""

    host: str
    """hostname of the server for the auth & acl check"""
    port: int
    """port of the server for the auth & acl check"""
    request_method: RequestMethod = RequestMethod.GET
    """send the request as a GET, POST or PUT"""
    params_mode: ParamsMode = ParamsMode.JSON  # see docs/plugins/http.md for additional details
    """send the request with `JSON` or `FORM` data. *additional details below*"""
    response_mode: ResponseMode = ResponseMode.JSON  # see docs/plugins/http.md for additional details
    """expected response from the auth/acl server. `STATUS` (code), `JSON`, or `TEXT`. *additional details below*"""
    with_tls: bool = False
    """http or https"""
    user_agent: str = "amqtt"
    """the 'User-Agent' header sent along with the request"""
    superuser_uri: str | None = None
    """URI to verify if the user is a superuser (e.g. '/superuser'), `None` if superuser is not supported"""
    timeout: int = 5
    """duration, in seconds, to wait for the HTTP server to respond"""


class AuthHttpPlugin(BasePlugin[BrokerContext]):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        self.http = ClientSession(headers = {"User-Agent": self.config.user_agent})

        match self.config.request_method:
            case RequestMethod.GET:
                self.method = self.http.get
            case RequestMethod.PUT:
                self.method = self.http.put
            case _:
                self.method = self.http.post

    async def on_broker_pre_shutdown(self) -> None:
        await self.http.close()

    @staticmethod
    def _is_2xx(r: ClientResponse) -> bool:
        return HTTP_2xx_MIN <= r.status <= HTTP_2xx_MAX

    @staticmethod
    def _is_4xx(r: ClientResponse) -> bool:
        return HTTP_4xx_MIN <= r.status <= HTTP_4xx_MAX

    def _get_params(self, payload: dict[str, Any]) -> dict[str, Any]:
        match self.config.params_mode:
            case ParamsMode.FORM:
                match self.config.request_method:
                    case RequestMethod.GET:
                        kwargs = { "params": payload }
                    case _: # POST, PUT
                        d: Any = FormData(payload)
                        kwargs = {"data": d}
            case _:  # JSON
                kwargs = { "json": payload}
        return kwargs

    async def _send_request(self, url: str, payload: dict[str, Any]) -> bool|None: # pylint: disable=R0911

        kwargs = self._get_params(payload)

        async with self.method(url, **kwargs) as r:
            logger.debug(f"http request returned {r.status}")

            match self.config.response_mode:
                case ResponseMode.TEXT:
                    return self._is_2xx(r) and (await r.text()).lower() == "ok"
                case ResponseMode.STATUS:
                    if self._is_2xx(r):
                        return True
                    if self._is_4xx(r):
                        return False
                    # any other code
                    return None
                case _:
                    if not self._is_2xx(r):
                        return False
                    data: dict[str, Any] = await r.json()
                    data = {k.lower():v for k,v in data.items()}
                    return data.get("ok", None)

    def get_url(self, uri: str) -> str:
        return f"{'https' if self.config.with_tls else 'http'}://{self.config.host}:{self.config.port}{uri}"


class UserAuthHttpPlugin(AuthHttpPlugin, BaseAuthPlugin):

    async def authenticate(self, *, session: Session) -> bool | None:
        d = {"username": session.username, "password": session.password, "client_id": session.client_id}
        return await self._send_request(self.get_url(self.config.user_uri), d)

    @dataclass
    class Config(HttpConfig):
        """Configuration for the HTTP Auth Plugin."""

        user_uri: str = "/user"
        """URI of the auth check."""


class TopicAuthHttpPlugin(AuthHttpPlugin, BaseTopicPlugin):

    async def topic_filtering(self, *,
                        session: Session | None = None,
                        topic: str | None = None,
                        action: Action | None = None) -> bool | None:
        if not session:
            return None
        acc = 0
        match action:
            case Action.PUBLISH:
                acc = 2
            case Action.SUBSCRIBE:
                acc = 4
            case Action.RECEIVE:
                acc = 1

        d = {"username": session.username, "client_id": session.client_id, "topic": topic, "acc": acc}
        return await self._send_request(self.get_url(self.config.topic_uri), d)

    @dataclass
    class Config(HttpConfig):
        """Configuration for the HTTP Topic Plugin."""

        topic_uri: str = "/acl"
        """URI of the topic check."""
