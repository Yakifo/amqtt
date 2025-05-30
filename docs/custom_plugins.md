# Custom Plugins

With the aMQTT Broker plugins framework, one can add additional functionality to the broker without
having to subclass or rewrite any of the core broker logic. To define a custom list of plugins to be loaded,
add this section to your `pyproject.toml`"

```toml
[project.entry-points."mypackage.mymodule.plugins"]
plugin_alias = "module.submodule.file:ClassName"
```

and specify the namespace when instantiating the broker:

```python
from amqtt.broker import Broker

broker = Broker(plugin_namespace='mypackage.mymodule.plugins')

```

Each plugin has access to the full configuration file through the provided `BaseContext` and can define
its own variables to configure its behavior.

::: amqtt.plugins.manager.BasePlugin

Plugins that are defined in the`project.entry-points` are loaded and notified of events by when the subclass 
implements one or more of these methods:

- `on_mqtt_packet_sent`
- `on_mqtt_packet_received`
- `on_broker_pre_start`
- `on_broker_post_start`
- `on_broker_pre_shutdown`
- `on_broker_post_shutdown`
- `on_broker_client_connected`
- `on_broker_client_disconnected`
- `on_broker_client_subscribed`
- `on_broker_client_unsubscribed`
- `on_broker_message_received`


## Authentication Plugins

Of the plugins listed in `project.entry-points`, one or more can be used to validate client sessions
by specifying their alias in `auth` > `plugins` section of the config:

```yaml
auth:
  plugins:
    - plugin_alias_name
```

These plugins should subclass from `BaseAuthPlugin` and implement the `authenticate` method.

::: amqtt.plugins.authentication.BaseAuthPlugin

## Topic Filter Plugins

Of the plugins listed in `project.entry-points`, one or more can be used to determine topic access
by specifying their alias in `topic-check` > `plugins` section of the config:

```yaml
topic-check:
  enable: True
  plugins:
    - plugin_alias_name
```

These plugins should subclass from `BaseTopicPlugin` and implement the `topic_filtering` method.


::: amqtt.plugins.topic_checking.BaseTopicPlugin
