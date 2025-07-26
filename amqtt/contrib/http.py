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
from amqtt.plugins.base import BaseAuthPlugin, BaseTopicPlugin
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


class HttpAuthTopicPlugin(BaseAuthPlugin, BaseTopicPlugin):

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

    async def authenticate(self, *, session: Session) -> bool | None:
        d = {"username": session.username, "password": session.password, "client_id": session.client_id}
        return await self._send_request(self.get_url(self.config.user_uri), d)

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
    class Config:
        """Configuration for the HTTP Auth & ACL Plugin.

        Members:
            - host *(str) hostname of the server for the auth & acl check
            - port *(int) port of the server for the auth & acl check
            - user_uri *(str) uri of the topic check (e.g. '/user')
            - topic_uri *(str) uri of the topic check (e.g. '/acl')
            - request_method *(RequestMethod) send the request as a GET, POST or PUT
            - params_mode *(ParamsMode) send the request with json or form data
            - response_mode *(ResponseMode) expected response from the auth/acl server. STATUS (code), JSON, or TEXT.
            - user_agent *(str) the 'User-Agent' header sent along with the request

        ParamsMode:

        for user authentication, the http server will receive in json or form format the following:
            - username *(str)*
            - password *(str)*
            - client_id *(str)*

        for superuser validation, the http server will receive in json or form format the following:
            - username *(str)*

        for acl check, the http server will receive in json or form format the following:
            - username *(str)*
            - client_id *(str)*
            - topic *(str)*
            - acc *(int)* client can receive (1), can publish(2), can receive & publish (3) and can subscribe (4)
        """

        host: str
        port: int
        user_uri: str
        topic_uri: str
        request_method: RequestMethod = RequestMethod.GET
        params_mode: ParamsMode = ParamsMode.JSON
        response_mode: ResponseMode = ResponseMode.JSON
        with_tls: bool = False
        user_agent: str = "amqtt"

        superuser_uri: str | None = None
        timeout: int = 5
