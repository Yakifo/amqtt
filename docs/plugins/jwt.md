# Authentication & Authorization from JWT

- `amqtt.contrib.jwt.UserAuthJwtPlugin` (client authentication)
- `amqtt.contrib.jwt.TopicAuthJwtPlugin` (topic authorization) 

Plugin to determine user authentication and topic authorization based on claims in a JWT.

# User Authentication

For auth, the JWT should include a key as specified in the configuration as `user_clam`:

```python
from datetime import datetime, UTC, timedelta
claims = {
    "username": "example_user",
    "exp": datetime.now(UTC) + timedelta(hours=1),
}
```

::: amqtt.contrib.jwt.UserAuthJwtPlugin.Config
    options:
      show_source: false
      heading_level: 4
      extra:
        class_style: "simple"


# Topic Authorization

For authorizing a client for certain topics, the token should also include claims for publish, subscribe and receive;
keys based on how `publish_claim`, `subscribe_claim` and `receive_claim` are specified in the plugin's configuration.

```python
from datetime import datetime, UTC, timedelta

    claims = {
        "username": "example_user",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "publish_acl": ['my/topic/#', 'my/+/other'],
        "subscribe_acl": ['my/+/other'],
        "receive_acl": ['#']
    }
```

::: amqtt.contrib.jwt.TopicAuthJwtPlugin.Config
    options:
      show_source: false
      heading_level: 4
      extra:
        class_style: "simple"
