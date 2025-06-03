# Client Configuration

This configuration structure is valid as a python dictionary passed to the `amqtt.broker.MQTTClient` class's `__init__` method or
as a yaml formatted file passed to the `amqtt_pub` script.

### `keep_alive` *(int)*

Keep-alive timeout sent to the broker. Defaults to `10` seconds.

### `ping_delay` *(int)*

Auto-ping delay before keep-alive timeout. Defaults to 1. Setting to `0` will disable to 0 and may lead to broker disconnection.

### `default_qos` *(int: 0-2)*

Default QoS for messages published. Defaults to 0.


### `default_retain` *(bool)*

Default retain value to messages published. Defaults to `false`.


### `auto_reconnect` *(bool)*

Enable or disable auto-reconnect if connection with the broker is interrupted. Defaults to `false`.

### `reconnect_retries` *(int)*
 
Maximum reconnection retries. Defaults to `2`. Negative value will cause client to reconnect infinitely.

### `reconnect_max_interval` *(int)*

Maximum interval between 2 connection retry. Defaults to `10`.

### `topics` *(list[mapping])*

Specify the topics and what flags should be set for messages published to them.

- `<topic>`: Named listener
    - `qos` *(int, 0-3)*: 
    - `retain` *(bool)*: 


## Default Configuration

```yaml
--8<-- "../amqtt/amqtt/scripts/default_client.yaml"
```

## Example

```yaml

keep_alive: 10
ping_delay: 1
default_qos': 0
default_retain: false
auto_reconnect: true
reconnect_max_interval: 5,
reconnect_retries: 10
topics:
   test:
    qos: 0
   some_topic:
     qos: 2
     retain: true
```
