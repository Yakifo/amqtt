from __future__ import annotations

from django.apps import AppConfig


class AmqttDjangoConfig(AppConfig):  # type: ignore[misc]
    """Django app configuration for amqtt's optional Django integration."""

    default_auto_field = "django.db.models.BigAutoField"
    label = "amqtt_django"
    name = "amqtt.contrib.django"
    verbose_name = "amqtt Django integration"
