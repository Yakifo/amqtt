import asyncio
import ldap
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from amqtt.broker import BrokerContext, Broker
from amqtt.client import MQTTClient
from amqtt.contexts import BrokerConfig, ListenerConfig, ClientConfig, Action
from amqtt.contrib.ldap import UserAuthLdapPlugin, TopicAuthLdapPlugin
from amqtt.errors import ConnectError
from amqtt.session import Session


# Pin the project name to avoid creating multiple stacks
@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    return "openldap"

# Stop the stack before starting a new one
@pytest.fixture(scope="session")
def docker_setup():
    return ["down -v", "up --build -d"]

@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return Path(pytestconfig.rootdir) / "tests/fixtures/ldap" / "docker-compose.yml"

@pytest.fixture(scope="session")
def ldap_service_docker(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""

    # `port_for` takes a container port and returns the corresponding host port
    port = docker_services.port_for("openldap", 389)
    url = "ldap://{}:{}".format(docker_ip, port)
    time.sleep(2)
    return url

@pytest.fixture(scope="session")
def ldap_service_mock():
    """Ensure that HTTP service is up and responsive."""

    # `port_for` takes a container port and returns the corresponding host port
    url = "ldap://localhost:0"
    mock_ldap_object = MagicMock()

    def mock_simple_s(*args, **kwargs):
        return [ ('dn', {'uid':'jdoe', 'publishACL':[b'my/topic/one', b'my/topic/two']}), ]

    def mock_simple_bind_s(*args):
        p = args[1]
        if p in ("adminpassword", "johndoepassword"):
            return
        raise ldap.INVALID_CREDENTIALS

    mock_ldap_object.search_s.side_effect = mock_simple_s
    mock_ldap_object.simple_bind_s.side_effect = mock_simple_bind_s
    with patch("ldap.initialize", return_value=mock_ldap_object):
        yield url

@pytest.fixture(scope="session")
def ldap_service(request):
    mode = request.config.getoption("--mock-docker")
    if mode:
        return request.getfixturevalue("ldap_service_mock")
    return request.getfixturevalue("ldap_service_docker")


@pytest.mark.asyncio
async def test_ldap_user_plugin(ldap_service):
    ctx = BrokerContext(Broker())
    ctx.config = UserAuthLdapPlugin.Config(
        server=ldap_service,
        base_dn="dc=amqtt,dc=io",
        user_attribute="uid",
        bind_dn="cn=admin,dc=amqtt,dc=io",
        bind_password="adminpassword",
    )
    ldap_plugin = UserAuthLdapPlugin(context=ctx)

    s = Session()
    s.username = "jdoe"
    s.password = "johndoepassword"

    assert await ldap_plugin.authenticate(session=s), "could not authenticate user"

@pytest.mark.asyncio
async def test_ldap_user(ldap_service):

    cfg = BrokerConfig(
        listeners={ 'default' : ListenerConfig() },
        plugins={
            'amqtt.contrib.ldap.UserAuthLdapPlugin': {
                'server': ldap_service,
                'base_dn': 'dc=amqtt,dc=io',
                'user_attribute': 'uid',
                'bind_dn': 'cn=admin,dc=amqtt,dc=io',
                'bind_password': 'adminpassword',
            },
        }
    )

    broker = Broker(config=cfg)
    await broker.start()

    await asyncio.sleep(0.1)

    client = MQTTClient(config=ClientConfig(auto_reconnect=False))
    await client.connect('mqtt://jdoe:johndoepassword@127.0.0.1:1883')
    await asyncio.sleep(0.1)
    await client.publish('my/topic', b'my message')
    await asyncio.sleep(0.1)
    await client.disconnect()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_ldap_user_invalid_creds(ldap_service):

    cfg = BrokerConfig(
        listeners={ 'default' : ListenerConfig() },
        plugins={
            'amqtt.contrib.ldap.UserAuthLdapPlugin': {
                'server': ldap_service,
                'base_dn': 'dc=amqtt,dc=io',
                'user_attribute': 'uid',
                'bind_dn': 'cn=admin,dc=amqtt,dc=io',
                'bind_password': 'adminpassword',
            },
        }
    )

    broker = Broker(config=cfg)
    await broker.start()

    await asyncio.sleep(0.1)

    client = MQTTClient(config=ClientConfig(auto_reconnect=False))
    with pytest.raises(ConnectError):
        await client.connect('mqtt://jdoe:wrongpassword@127.0.0.1:1883')

    await broker.shutdown()


@pytest.mark.asyncio
async def test_ldap_topic_plugin(ldap_service):
    ctx = BrokerContext(Broker())
    ctx.config = TopicAuthLdapPlugin.Config(
        server=ldap_service,
        base_dn="dc=amqtt,dc=io",
        user_attribute="uid",
        bind_dn="cn=admin,dc=amqtt,dc=io",
        bind_password="adminpassword",
        publish_attribute="publishACL",
        subscribe_attribute="subscribeACL",
        receive_attribute="receiveACL"
    )
    ldap_plugin = TopicAuthLdapPlugin(context=ctx)

    s = Session()
    s.username = "jdoe"
    s.password = "wrongpassword"

    assert await ldap_plugin.topic_filtering(session=s, topic='my/topic/one', action=Action.PUBLISH), "access not granted"
