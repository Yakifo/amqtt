# Client Configuration

This configuration structure is either a `amqtt.contexts.ClientConfig` or a python dictionary with identical structure
when instantiating `amqtt.broker.MQTTClient` or as a yaml formatted file passed to the `amqtt_pub` script.

If not specified, the `MQTTClient()` will be started with the default `ClientConfig()`, as represented in yaml format:

```yaml
---
keep_alive: 10
ping_delay: 1
default_qos: 0
default_retain: false
auto_reconnect: true
connection_timeout: 60
reconnect_retries: 2
reconnect_max_interval: 10
cleansession: true
broker:
  uri: "mqtt://127.0.0.1"
plugins:
  amqtt.plugins.logging_amqtt.PacketLoggerPlugin:
```

::: amqtt.contexts.ClientConfig
    options:
      heading_level: 3
      extra:
        class_style: "simple"

::: amqtt.contexts.TopicConfig
    options:
      heading_level: 3
      extra:
        class_style: "simple"

::: amqtt.contexts.WillConfig
    options:
      heading_level: 3
      extra:
        class_style: "simple"

::: amqtt.contexts.ConnectionConfig
    options:
      heading_level: 3
      extra:
        class_style: "simple"



## Example

A more expansive `ClientConfig` in equivalent yaml format:

```yaml

keep_alive: 10
ping_delay: 1
default_qos: 0
default_retain: false
auto_reconnect: true
reconnect_max_interval: 5
reconnect_retries: 10
topics:
   topic/subtopic:
    qos: 0
   topic/other:
     qos: 2
     retain: true
will:
   topic: will/messages
   message: "client ABC has disconnected"
   qos: 1
   retain: false
broker:
   uri: 'mqtt://localhost:1883'
   cafile: '/path/to/ca/file'
plugins:
  - amqtt.plugins.logging_amqtt.PacketLoggerPlugin:
```
