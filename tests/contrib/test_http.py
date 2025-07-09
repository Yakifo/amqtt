import logging

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.web import Response

from amqtt.broker import BrokerContext, Broker
from amqtt.contexts import Action
from amqtt.contrib.http import HttpAuthACL, ParamsMode, ResponseMode, RequestMethod
from amqtt.session import Session

logger = logging.getLogger(__name__)


def determine_auth_response_mode(d) -> Response:
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
        return determine_auth_response_mode(d)

    async def post(self) -> Response:
        d = dict(await self.request.json())
        return determine_auth_response_mode(d)

    async def put(self) -> Response:
        d = dict(await self.request.json())
        return determine_auth_response_mode(d)

class FormAuthView(web.View):

    async def get(self) -> Response:
        d = self.request.query
        return determine_auth_response_mode(d)

    async def post(self) -> Response:
        d = dict(await self.request.post())
        return determine_auth_response_mode(d)

    async def put(self) -> Response:
        d = dict(await self.request.post())
        return determine_auth_response_mode(d)


@pytest.fixture
async def empty_broker():
    config = {'listeners': {'default': { 'type': 'tcp', 'bind': '127.0.0.1:1883'}}, 'plugins': {}}
    broker = Broker(config)
    yield broker


@pytest_asyncio.fixture
async def http_auth_server():
    app = web.Application()
    app.add_routes([
        web.view('/user/json', JsonAuthView),
        web.view('/user/form', FormAuthView),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8080)
    await site.start()

    yield f"http://127.0.0.1:8080"

    await runner.cleanup()


def test_server_up_and_down(http_auth_server):
    pass

def generate_use_cases(root_url):
    # generate all variations of:
    # ('/user/json', RequestMethod.GET, ParamsMode.JSON, ResponseMode.JSON, 'json', 'json', True),

    cases: list[tuple[str, RequestMethod, ParamsMode, ResponseMode, str, str, bool]] = []
    for request in RequestMethod:
        for params in ParamsMode:
            for response in ResponseMode:
                url = f'/{root_url}/json' if params == ParamsMode.JSON else f'/{root_url}/form'
                for is_authenticated in [True, False]:
                    prefix = '' if is_authenticated else 'not'
                    case = (url, request, params, response, response.value, f"{prefix}{response.value}", is_authenticated)
                    cases.append(case)
    return cases

def test_generated_use_cases():
    cases = generate_use_cases('user')
    assert len(cases) == 36


@pytest.mark.parametrize("url,request_method,params_mode,response_mode,username,password,is_authenticated",
                         generate_use_cases('user'))
@pytest.mark.asyncio
async def test_request_auth_response(empty_broker, http_auth_server, url,
                                       request_method, params_mode, response_mode,
                                       username, password, is_authenticated):

    context = BrokerContext(broker=empty_broker)
    context.config = HttpAuthACL.Config(
        host="127.0.0.1",
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


def determine_acl_response(d) -> Response:
    assert 'username' in d
    assert 'client_id' in d
    assert 'topic' in d
    assert 'acc' in d
    if d['username'] == 'json':
        return web.json_response({'Ok': d['username'] == d['client_id']})
    elif d['username'] == 'status':
        return web.Response(status=200) if d['username'] == d['client_id'] else web.Response(status=400)
    else: # text
        return web.Response(text='ok' if d['username'] == d['client_id'] else 'error')


class JsonACLView(web.View):

    async def get(self) -> Response:
        d = await self.request.json()
        return determine_acl_response(d)

    async def post(self) -> Response:
        d = dict(await self.request.json())
        return determine_acl_response(d)

    async def put(self) -> Response:
        d = dict(await self.request.json())
        return determine_acl_response(d)


class FormACLView(web.View):

    async def get(self) -> Response:
        d = self.request.query
        return determine_acl_response(d)

    async def post(self) -> Response:
        d = dict(await self.request.post())
        return determine_acl_response(d)

    async def put(self) -> Response:
        d = dict(await self.request.post())
        return determine_acl_response(d)


@pytest_asyncio.fixture
async def http_acl_server():
    app = web.Application()
    app.add_routes([
        web.view('/acl/json', JsonACLView),
        web.view('/acl/form', FormACLView),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8080)
    await site.start()

    yield f"http://127.0.0.1:8080"

    await runner.cleanup()


@pytest.mark.parametrize("url,request_method,params_mode,response_mode,username,client_id,is_authenticated",
                             generate_use_cases('acl'))
@pytest.mark.asyncio
async def test_request_acl_response(empty_broker, http_acl_server, url,
                                     request_method, params_mode, response_mode,
                                     username, client_id, is_authenticated):

    # url = '/acl/json'
    # request_method = RequestMethod.GET
    # params_mode = ParamsMode.JSON
    # response_mode = ResponseMode.JSON

    context = BrokerContext(broker=empty_broker)
    context.config = HttpAuthACL.Config(
        host="127.0.0.1",
        port=8080,
        user_uri='/user',
        acl_uri=url,
        request_method=request_method,
        params_mode=params_mode,
        response_mode=response_mode,
    )
    http_acl = HttpAuthACL(context)

    s = Session()
    s.username = username
    s.client_id = client_id
    t = 'my/topic'
    a = Action.PUBLISH
    logger.debug(f"username: {username}, client_id: {client_id}, topic: {t}")
    assert await http_acl.topic_filtering(session=s, topic=t, action=a) == is_authenticated