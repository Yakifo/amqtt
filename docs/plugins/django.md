# Django Auth

`amqtt.contrib.django` provides an optional Django app and broker plugins for authenticating MQTT clients with Django-owned users.

Install the contrib extra:

```bash
pip install 'amqtt[contrib]'
```

Add the app to `INSTALLED_APPS` and run migrations:

```python
INSTALLED_APPS = [
    # ...
    "amqtt.contrib.django",
]
```

```bash
python manage.py migrate amqtt_django
```

Create MQTT tokens with the included model:

```python
from amqtt.contrib.django.models import MqttToken

token, raw_key = MqttToken.issue(user)
```

Store `raw_key` securely and send it as the MQTT password. The database stores only a SHA-256 digest of the token.

The included concrete model is built from `AbstractMqttToken`, which projects can subclass when they need extra fields:

```python
from django.db import models

from amqtt.contrib.django.models import AbstractMqttToken


class ProjectMqttToken(AbstractMqttToken):
    device_name = models.CharField(max_length=128, blank=True)
```

Use the custom model in your broker plugin config after creating migrations for your Django app.

Configure broker plugins with:

```yaml
plugins:
  amqtt.contrib.django.plugins.DjangoAuthPlugin:
    token_model: amqtt_django.MqttToken
  amqtt.contrib.django.plugins.UserTopicACLPlugin:
```

## Example Broker Config

```python
broker_config = {
    "sys_interval": 0,
    "plugins": {
        "amqtt.contrib.django.plugins.DjangoAuthPlugin": {
            "token_model": "amqtt_django.MqttToken",
            "service_user_id": "service",
            "service_token": "shared-secret",
        },
        "amqtt.contrib.django.plugins.UserTopicACLPlugin": {},
    },
}
```

::: amqtt.contrib.django.plugins.DjangoAuthPlugin.Config
    options:
      show_source: false
      heading_level: 3
      extra:
        class_style: "simple"

By default, `DjangoAuthPlugin` uses `amqtt_django.MqttToken`. A project can provide its own compatible model in the plugin
configuration:

```python
broker_config = {
    "plugins": {
        "amqtt.contrib.django.plugins.DjangoAuthPlugin": {
            "token_model": "myapp.MqttToken",
        },
    },
}
```

The custom model must provide:

- `get_active_for_key(raw_key: str)`
- `user_id`
- `DoesNotExist`

Subclassing `AbstractMqttToken` provides this contract automatically, but the plugin does not require inheritance.

Optional service publisher credentials are configured with the plugin's `service_user_id` and `service_token` options.

::: amqtt.contrib.django.models.AbstractMqttToken
    options:
      show_source: false
      heading_level: 3
      extra:
        class_style: "simple"

::: amqtt.contrib.django.models.MqttToken
    options:
      show_source: false
      heading_level: 3
      extra:
        class_style: "simple"
