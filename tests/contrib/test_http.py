import logging
from enum import Enum, auto

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.web import Response

from amqtt.broker import BrokerContext, Broker
from amqtt.contexts import Action
from amqtt.contrib.http import UserAuthHttpPlugin, TopicAuthHttpPlugin, ParamsMode, ResponseMode, RequestMethod
from amqtt.session import Session

logger = logging.getLogger(__name__)


def determine_response(d, matcher_field) -> Response:
    """The request's parameters determine what response is expected."""
    if d['username'] == 'json':
        # special case, i_am_null respond with None
        if d[matcher_field] == 'i_am_null':
            return web.json_response({'Ok': None})
        # otherwise, respond depending on if username and client_id match
        return web.json_response({'Ok': d['username'] == d[matcher_field]})
    elif d['username'] == 'status':
        if d[matcher_field] == 'i_am_null':
            return web.Response(status=500)
        return web.Response(status=200) if d['username'] == d[matcher_field] else web.Response(status=400)
    else: # text
        return web.Response(text='ok' if d['username'] == d[matcher_field] else 'error')


@pytest.fixture
async def empty_broker():
    config = {'listeners': {'default': { 'type': 'tcp', 'bind': '127.0.0.1:1883'}}, 'plugins': {}}
    broker = Broker(config)
    yield broker


async def all_request_handler(request: web.Request) -> Response:
    """The url and method type is used determine how the data was passed to the request."""
    if 'form' in str(request.url):
        if request.method == 'GET':
            d = request.query
        else:
            d = dict(await request.post())
    else:
        d = dict(await request.json())

    if '/user' in str(request.url):
        matcher = 'password'
        assert 'username' in d
        assert 'password' in d
        assert 'client_id' in d
    else:
        assert 'username' in d
        assert 'client_id' in d
        assert 'topic' in d
        assert 'acc' in d
        assert 1 <= int(d['acc']) <= 4
        matcher = 'client_id'

    return determine_response(d, matcher)


@pytest_asyncio.fixture
async def http_server():
    app = web.Application()

    # create all the routes for the various configuration options to handle the various use cases
    routes = []
    for test_kind in ('user', 'acl'):
        for test_data in ('json', 'form'):
            for method in ('get', 'post', 'put'):
                func_method = getattr(web, method)
                routes.append(func_method(f'/{test_kind}/{test_data}', all_request_handler))

    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8080)
    await site.start()

    yield f"http://127.0.0.1:8080"

    await runner.cleanup()


def test_server_up_and_down(http_server):
    pass


class TypeOfHttpTest(Enum):
    AUTH = auto()
    ACL = auto()


def generate_use_cases(kind: TypeOfHttpTest):
    # generate all variations of the plugin's configuration options for both auth and topic
    # e.g. (TestKind.AUTH, '/user/json', RequestMethod.GET, ParamsMode.JSON, ResponseMode.JSON, 'json', 'json', True),

    cases: list[tuple[str, str, RequestMethod, ParamsMode, ResponseMode, str, str, bool]] = []

    root_url = 'user' if kind == TypeOfHttpTest.AUTH else 'acl'
    for request in RequestMethod:
        for params in ParamsMode:
            for response in ResponseMode:
                url = f'/{root_url}/json' if params == ParamsMode.JSON else f'/{root_url}/form'
                for is_authenticated in [True, False, None]:
                    if is_authenticated is None:
                        pwd = 'i_am_null'
                    elif is_authenticated:
                        pwd = f'{response.value}'
                    else:
                        pwd = f'not{response.value}'

                    if response == ResponseMode.TEXT and is_authenticated is None:
                        is_authenticated = False

                    case = (kind, url, request, params, response, response.value, f"{pwd}", is_authenticated)
                    cases.append(case)
    return cases

def test_generated_use_cases():
    cases = generate_use_cases(kind=TypeOfHttpTest.AUTH)
    assert len(cases) == 54


@pytest.mark.parametrize("kind,url,request_method,params_mode,response_mode,username,matcher,is_allowed",
                         generate_use_cases(TypeOfHttpTest.AUTH))
@pytest.mark.asyncio
async def test_request_auth_response(empty_broker, http_server, kind, url,
                                     request_method, params_mode, response_mode,
                                     username, matcher, is_allowed):

    context = BrokerContext(broker=empty_broker)
    context.config = UserAuthHttpPlugin.Config(
        host="127.0.0.1",
        port=8080,
        user_uri=url,
        request_method=request_method,
        params_mode=params_mode,
        response_mode=response_mode,
    )
    http_acl = UserAuthHttpPlugin(context)
    logger.warning(f'kind is {kind}')

    session = Session()
    session.client_id = "my_client_id"
    session.username = username
    session.password = matcher
    assert await http_acl.authenticate(session=session) == is_allowed

    await http_acl.on_broker_pre_shutdown()


@pytest.mark.parametrize("kind,url,request_method,params_mode,response_mode,username,matcher,is_allowed",
                         generate_use_cases(TypeOfHttpTest.ACL))
@pytest.mark.asyncio
async def test_request_topic_response(empty_broker, http_server, kind, url,
                                     request_method, params_mode, response_mode,
                                     username, matcher, is_allowed):
    context = BrokerContext(broker=empty_broker)
    context.config = TopicAuthHttpPlugin.Config(
        host="127.0.0.1",
        port=8080,
        topic_uri=url,
        request_method=request_method,
        params_mode=params_mode,
        response_mode=response_mode,
    )
    http_acl = TopicAuthHttpPlugin(context)

    s = Session()
    s.username = username
    s.client_id = matcher
    t = 'my/topic'
    a = Action.PUBLISH
    assert await http_acl.topic_filtering(session=s, topic=t, action=a) == is_allowed

    await http_acl.on_broker_pre_shutdown()



    # if kind == TestKind.ACL:

    # else: