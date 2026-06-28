from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from django.conf import settings

_DB_DIR = tempfile.TemporaryDirectory(prefix="amqtt-django-test-")
_DB_PATH = Path(_DB_DIR.name) / "db.sqlite3"

if not settings.configured:
    settings.configure(
        SECRET_KEY="amqtt-test-secret",
        USE_TZ=True,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(_DB_PATH),
            },
        },
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "amqtt.contrib.django",
        ],
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )

import django

django.setup()

from amqtt.broker import Broker, BrokerContext
from amqtt.contexts import Action, BaseContext
from amqtt.contrib.django.models import AbstractMqttToken, MqttToken
from amqtt.contrib.django.plugins import DEFAULT_TOKEN_MODEL, DjangoAuthPlugin, UserTopicACLPlugin
from amqtt.plugins.manager import PluginManager
from amqtt.session import Session
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.fixture(scope="module", autouse=True)
def django_database() -> None:
    call_command("migrate", verbosity=0, interactive=False)


@pytest.fixture(autouse=True)
def clean_django_database(django_database: None) -> None:
    call_command("flush", verbosity=0, interactive=False)


@pytest.fixture
def user():
    user_model = get_user_model()
    return user_model.objects.create_user(username="mqtt-user")


@pytest.fixture
def issued_token(user) -> tuple[MqttToken, str]:
    return MqttToken.issue(user)


def _auth_plugin(
    *,
    token_model: str = DEFAULT_TOKEN_MODEL,
    service_user_id: str | None = None,
    service_token: str | None = None,
) -> DjangoAuthPlugin:
    context = BrokerContext(Broker())
    context.config = DjangoAuthPlugin.Config(
        token_model=token_model,
        service_user_id=service_user_id,
        service_token=service_token,
    )
    return DjangoAuthPlugin(context)


def _topic_plugin() -> UserTopicACLPlugin:
    context = BrokerContext(Broker())
    context.config = UserTopicACLPlugin.Config()
    return UserTopicACLPlugin(context)


def test_mqtt_token_issue_stores_digest_only(user) -> None:
    token, raw_key = MqttToken.issue(user)

    assert raw_key
    assert token.key_digest != raw_key
    assert token.key_digest == MqttToken.digest_key(raw_key)
    assert token.matches_key(raw_key)
    assert MqttToken.get_active_for_key(raw_key) == token


def test_mqtt_token_revoke_removes_token_from_active_lookup(user) -> None:
    token, raw_key = MqttToken.issue(user)

    token.revoke()

    with pytest.raises(MqttToken.DoesNotExist):
        MqttToken.get_active_for_key(raw_key)


def test_mqtt_token_abstract_base_contract() -> None:
    assert AbstractMqttToken._meta.abstract
    assert issubclass(MqttToken, AbstractMqttToken)
    assert MqttToken.generate_key() != MqttToken.generate_key()


def test_django_auth_plugin_loads_amqtt_plugin_config() -> None:
    context = BaseContext()
    context.config = {
        "plugins": {
            "amqtt.contrib.django.plugins.DjangoAuthPlugin": {
                "token_model": "amqtt_django.MqttToken",
                "service_user_id": "service",
                "service_token": "secret",
            },
        },
    }

    manager = PluginManager("amqtt.broker.plugins", context=context)
    plugin = manager.get_plugin("DjangoAuthPlugin")

    assert isinstance(plugin, DjangoAuthPlugin)
    assert plugin.config.token_model == "amqtt_django.MqttToken"
    assert plugin.config.service_user_id == "service"
    assert plugin.config.service_token == "secret"


@pytest.mark.asyncio
async def test_django_auth_plugin_accepts_active_token(user, issued_token) -> None:
    _, raw_key = issued_token
    plugin = _auth_plugin()
    session = Session()
    session.username = str(user.id)
    session.password = raw_key

    assert await plugin.authenticate(session=session) is True
    assert session._django_role == "user"  # noqa: SLF001


@pytest.mark.asyncio
async def test_django_auth_plugin_rejects_wrong_user(issued_token) -> None:
    _, raw_key = issued_token
    plugin = _auth_plugin()
    session = Session()
    session.username = "not-the-token-owner"
    session.password = raw_key

    assert await plugin.authenticate(session=session) is False
    assert not hasattr(session, "_django_role")


@pytest.mark.asyncio
async def test_django_auth_plugin_accepts_service_credentials() -> None:
    plugin = _auth_plugin(service_user_id="service", service_token="secret")
    session = Session()
    session.username = "service"
    session.password = "secret"

    assert await plugin.authenticate(session=session) is True
    assert session._django_role == "service"  # noqa: SLF001


@pytest.mark.asyncio
async def test_user_topic_acl_scopes_subscribers_to_own_updates() -> None:
    plugin = _topic_plugin()
    session = Session()
    session.username = "123"
    session._django_role = "user"  # noqa: SLF001

    assert await plugin.topic_filtering(session=session, topic="users/123/updates/new", action=Action.SUBSCRIBE) is True
    assert await plugin.topic_filtering(session=session, topic="users/456/updates/new", action=Action.SUBSCRIBE) is False


@pytest.mark.asyncio
async def test_user_topic_acl_allows_service_publish_only_to_update_topics() -> None:
    plugin = _topic_plugin()
    session = Session()
    session.username = "service"
    session._django_role = "service"  # noqa: SLF001

    assert await plugin.topic_filtering(session=session, topic="users/123/updates/new", action=Action.PUBLISH) is True
    assert await plugin.topic_filtering(session=session, topic="users/123/private/new", action=Action.PUBLISH) is False
