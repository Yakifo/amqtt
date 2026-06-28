from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING, ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


class AbstractMqttToken(models.Model):
    """Abstract hashed bearer token model for authenticating MQTT clients."""

    KEY_BYTES: ClassVar[int] = 32

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )
    key_digest = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Django model metadata."""

        abstract = True
        indexes = [models.Index(fields=["user", "revoked_at"])]  # noqa: RUF012

    def __str__(self) -> str:
        """Return a concise token description for Django admin and shell use."""
        return f"{self.__class__.__name__}(user={self.user_id}, created_at={self.created_at:%Y-%m-%d %H:%M:%S%z})"

    @classmethod
    def generate_key(cls) -> str:
        """Return a new raw token suitable for use as an MQTT password."""
        return secrets.token_urlsafe(cls.KEY_BYTES)

    @staticmethod
    def digest_key(raw_key: str) -> str:
        """Return the stable SHA-256 digest stored for a raw token."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user: AbstractBaseUser, raw_key: str | None = None) -> tuple[AbstractMqttToken, str]:
        """Create a token for a user and return ``(token, raw_key)``."""
        key = raw_key or cls.generate_key()
        token = cls.objects.create(user=user, key_digest=cls.digest_key(key))
        return token, key

    @classmethod
    def get_active_for_key(cls, raw_key: str) -> AbstractMqttToken:
        """Return the active token matching ``raw_key``."""
        return cls.objects.select_related("user").get(key_digest=cls.digest_key(raw_key), revoked_at__isnull=True)

    def matches_key(self, raw_key: str) -> bool:
        """Return whether ``raw_key`` matches this stored token digest."""
        return hmac.compare_digest(self.key_digest, self.digest_key(raw_key))

    def revoke(self) -> None:
        """Mark this token as revoked."""
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])


class MqttToken(AbstractMqttToken):
    """Concrete MQTT token model provided by the amqtt Django app."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="amqtt_tokens")
