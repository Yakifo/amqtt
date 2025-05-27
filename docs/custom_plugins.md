# Custom Plugins

Every plugin listed in the `project.entry-points` is loaded and notified of events
by defining any of the following methods:  

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

Of the plugins listed in `project.entry-points`, plugins can be used to validate client sessions
by specifying their alias in `auth` > `plugins` section of the config:

```yaml
auth:
  plugins:
    - plugin_alias_name
```

These plugins should sub-class from `BaseAuthPlugin` and implement the `authenticate` method.

::: amqtt.plugins.authentication.BaseAuthPlugin

## Topic Filter Plugins

Of the plugins listed in `project.entry-points`, plugins can be used to validate client sessions
by specifying their alias in `topic-check` > `plugins` section of the config:

```yaml
topic-check:
  plugins:
    - plugin_alias_name
```

These plugins should sub-class from `BaseTopicPlugin` and implement the `topic_filtering` method.


::: amqtt.plugins.topic_checking.BaseTopicPlugin
