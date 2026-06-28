"""AMQTT auth and topic-check plugins backed by Django's token store.

Implements the broker side of [ADR-006] push notifications:

- ``DjangoAuthPlugin`` authenticates a CONNECT by looking up an active
  ``MqttToken`` whose raw token equals ``password`` and confirming that the
  token's owner UUID equals ``username``. The service user authenticates the
  same way against a token configured in the plugin config.
- ``UserTopicACLPlugin`` only allows subscribers to subscribe to topics under
  ``users/<their-user-id>/updates/...``. The service user is allowed to publish
  to any ``users/.../updates/...`` topic so backend jobs can fan out per-user
  pushes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from amqtt.contexts import Action, BaseContext
from amqtt.plugins.authentication import BaseAuthPlugin
from amqtt.plugins.topic_checking import BaseTopicPlugin

if TYPE_CHECKING:
    from amqtt.session import Session

SERVICE_USER_SENTINEL = "service"
DEFAULT_TOKEN_MODEL = "amqtt_django.MqttToken"  # noqa: S105


def _build_user_topic_prefix(user_id: str) -> str:
    return f"users/{user_id}/updates/"


def _get_token_model(token_model_label: str) -> type:
    try:
        return apps.get_model(token_model_label, require_ready=True)
    except ValueError as exc:
        msg = "token_model must be in the form 'app_label.ModelName'"
        raise ImproperlyConfigured(msg) from exc
    except LookupError as exc:
        msg = f"token_model points to unknown model '{token_model_label}'"
        raise ImproperlyConfigured(msg) from exc


def _check_token(
    password: str,
    username: str,
    token_model_label: str,
    service_user_id: str | None,
    service_token: str | None,
) -> tuple[bool, str | None]:
    """Sync ORM check wrapped for the async broker.

    Returns ``(is_authenticated, role)`` where role is ``"service"`` for the
    service publish user, ``"user"`` for a regular browser subscriber, or
    ``None`` when authentication fails.
    """
    if service_user_id and service_token and username == service_user_id and password == service_token:
        return True, SERVICE_USER_SENTINEL

    token_model = _get_token_model(token_model_label)
    try:
        token = token_model.get_active_for_key(password)
    except token_model.DoesNotExist:
        return False, None

    if str(token.user_id) != username:
        return False, None
    return True, "user"


class DjangoAuthPlugin(BaseAuthPlugin):
    """Authenticate MQTT clients against Django-backed MQTT tokens."""

    def __init__(self, context: BaseContext) -> None:
        super().__init__(context)

    async def authenticate(self, *, session: Session) -> bool | None:
        username = session.username or ""
        password = session.password or ""
        if not username or not password:
            return False

        ok, role = await sync_to_async(_check_token)(
            password,
            username,
            self.config.token_model,
            self.config.service_user_id,
            self.config.service_token,
        )
        if not ok:
            return False
        # Stash the role on the session so the topic plugin can read it without
        # another DB round-trip.
        session._django_role = role  # noqa: SLF001
        return True

    @dataclass
    class Config:
        """Configuration for Django-backed MQTT authentication."""

        token_model: str = DEFAULT_TOKEN_MODEL
        """Django model label used for MQTT token lookup."""
        service_user_id: str | None = None
        """Optional MQTT username for a privileged service publisher."""
        service_token: str | None = None
        """Optional MQTT password for the privileged service publisher."""


class UserTopicACLPlugin(BaseTopicPlugin):
    """Enforce per-user topic ACLs for the push notification bus.

    Subscribers (regular users) may only subscribe to ``users/<their_id>/...``.
    The service user may publish anywhere under ``users/.../updates/...``.
    """

    async def topic_filtering(
        self,
        *,
        session: Session | None = None,
        topic: str | None = None,
        action: Action | None = None,
    ) -> bool | None:
        if session is None or topic is None or action is None:
            return False

        role = getattr(session, "_django_role", None)
        username = session.username or ""

        if action is Action.PUBLISH:
            # Browser clients never publish.
            if role != SERVICE_USER_SENTINEL:
                return False
            return topic.startswith("users/") and "/updates/" in topic

        # SUBSCRIBE or RECEIVE: scope to the authenticated user.
        prefix = _build_user_topic_prefix(username)
        return topic.startswith(prefix)
