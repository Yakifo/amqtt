import logging
from ast import Param
from asyncio import new_event_loop
from typing import Awaitable

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.web import Response, Request

from amqtt.broker import BrokerContext, Broker
from amqtt.contrib.http_acl import HttpAuthACL, ParamsMode, ResponseMode, RequestMethod
from amqtt.session import Session

logger = logging.getLogger(__name__)


def determine_response_mode(d) -> Response:
    assert 'username' in d
    assert 'password' in d
    assert 'client_id' in d
    if d['username'] == 'json':
        return web.json_response({'Ok': d['username'] == d['password']})
    elif d['username'] == 'status':
        return web.Response(status=200) if d['username'] == d['password'] else web.Response(status=400)
    else: # text
        return web.Response(text='ok' if d['username'] == d['password'] else 'error')


class JsonAuthView(web.View):

    async def get(self) -> Response:
        d = await self.request.json()
        return determine_response_mode(d)

    async def post(self) -> Response:
        d = dict(await self.request.json())
        return determine_response_mode(d)

    async def put(self) -> Response:
        d = dict(await self.request.json())
        return determine_response_mode(d)

class FormAuthView(web.View):

    async def get(self) -> Response:
        d = self.request.query
        return determine_response_mode(d)

    async def post(self) -> Response:
        d = dict(await self.request.post())
        return determine_response_mode(d)

    async def put(self) -> Response:
        d = dict(await self.request.post())
        return determine_response_mode(d)


@pytest.fixture
async def empty_broker():
    config = {'listeners': {'default': { 'type': 'tcp', 'bind': 'localhost:1883'}}, 'plugins': {}}
    broker = Broker(config)
    yield broker


@pytest_asyncio.fixture
async def http_acl_server():
    app = web.Application()
    app.add_routes([
        web.view('/user/json', JsonAuthView),
        web.view('/user/form', FormAuthView),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8080)
    await site.start()

    yield f"http://localhost:8080"

    await runner.cleanup()


def test_server_up_and_down(http_acl_server):
    pass

def generate_cases():
    # generate all variations of:
    # ('/user/json', RequestMethod.GET, ParamsMode.JSON, ResponseMode.JSON, 'json', 'json', True),

    cases: list[tuple[str, RequestMethod, ParamsMode, ResponseMode, str, str, bool]] = []
    for request in RequestMethod:
        for params in ParamsMode:
            for response in ResponseMode:
                url = '/user/json' if params == ParamsMode.JSON else '/user/form'
                for is_authenticated in [True, False]:
                    prefix = '' if is_authenticated else 'not'
                    case = (url, request, params, response, str(response), f"{prefix}{str(response)}", is_authenticated)
                    cases.append(case)
    return cases

def test_generated_cases():
    cases = generate_cases()
    assert len(cases) == 36


@pytest.mark.parametrize("url,request_method,params_mode,response_mode,username,password,is_authenticated",
                         generate_cases())
@pytest.mark.asyncio
async def test_request_params_response(empty_broker, http_acl_server, url,
                                       request_method, params_mode, response_mode,
                                       username, password, is_authenticated):

    context = BrokerContext(broker=empty_broker)
    context.config = HttpAuthACL.Config(
        host="localhost",
        port=8080,
        user_uri=url,
        acl_uri="/acl",
        request_method=request_method,
        params_mode=params_mode,
        response_mode=response_mode,
    )
    http_acl = HttpAuthACL(context)

    session = Session()
    session.client_id = "my_client_id"
    session.username = username
    session.password = password
    assert await http_acl.authenticate(session=session) == is_authenticated

    await http_acl.on_broker_pre_shutdown()
