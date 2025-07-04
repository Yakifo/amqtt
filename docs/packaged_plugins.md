# Existing Plugins

With the aMQTT plugins framework, one can add additional functionality without
having to rewrite core logic in the broker or client. Plugins can be loaded and configured using
the `plugins` section of the config file (or parameter passed to the class). 


## Broker

By default, `EventLoggerPlugin`, `PacketLoggerPlugin`, `AnonymousAuthPlugin` and `BrokerSysPlugin` are activated
and configured for the broker:

```yaml
--8<-- "amqtt/scripts/default_broker.yaml"
```


??? warning "Loading plugins from EntryPoints in `pyproject.toml` has been deprecated"

    Previously, all plugins were loaded from EntryPoints:

    ```toml
    --8<-- "pyproject.toml:included"
    ```

    But the same 4 plugins were activated in the previous default config:

    ```yaml
    --8<-- "samples/legacy.yaml"
    ```

## Client

By default, the `PacketLoggerPlugin` is  activated  and configured for the client:

```yaml
--8<-- "amqtt/scripts/default_client.yaml"
```

## Plugins

### Anonymous (Auth Plugin)

`amqtt.plugins.authentication.AnonymousAuthPlugin`

**Configuration**

```yaml
plugins:
  .
  .
  amqtt.plugins.authentication.AnonymousAuthPlugin:
      allow_anonymous: false
```

!!! danger
    even if `allow_anonymous` is set to `false`, the plugin will still allow access if a username is provided by the client


??? warning "EntryPoint-style configuration is deprecated"

    ```yaml
    auth:
      plugins:
        - auth_anonymous
      allow-anonymous: true # if false, providing a username will allow access
    
    ```

### Password File (Auth Plugin)

`amqtt.plugins.authentication.FileAuthPlugin`

clients are authorized by providing username and password, compared against file

**Configuration**

```yaml
plugins:
  amqtt.plugins.authentication.FileAuthPlugin:
      password_file: /path/to/password_file
```

??? warning "EntryPoint-style configuration is deprecated"
    ```yaml
    
    auth:
      plugins:
        - auth_file
      password-file: /path/to/password_file
    
    ```

**File Format**

The file includes `username:password` pairs, one per line.

The password should be encoded using sha-512 with `mkpasswd -m sha-512` or:

```python
import sys
from getpass import getpass
from passlib.hash import sha512_crypt

passwd = input() if not sys.stdin.isatty() else getpass()
print(sha512_crypt.hash(passwd))
```

### Taboo (Topic Plugin)

`amqtt.plugins.topic_checking.TopicTabooPlugin`

Prevents using topics named: `prohibited`, `top-secret`, and `data/classified`

**Configuration**

```yaml
plugins:
  amqtt.plugins.topic_checking.TopicTabooPlugin:
```

??? warning "EntryPoint-style configuration is deprecated"

    ```yaml
    topic-check:
      enabled: true
      plugins:
        - topic_taboo
    ```

### ACL (Topic Plugin)

`amqtt.plugins.topic_checking.TopicAccessControlListPlugin`

**Configuration**

- `acl` *(mapping)*: determines subscription access
   The list should be a key-value pair, where:
        `<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).


- `publish-acl` *(mapping)*: determines publish access. If absent, no restrictions are placed on client publishing. 
        `<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).

    !!! info "Reserved usernames"

        - The username `admin` is allowed access to all topics.
        - The username `anonymous` will control allowed topics, if using the `auth_anonymous` plugin.

```yaml
plugins:
  amqtt.plugins.topic_checking.TopicAccessControlListPlugin:
    acl:
      - username: ["list", "of", "allowed", "topics", "for", "subscribing"]
      - .
    publish_acl:
      - username: ["list", "of", "allowed", "topics", "for", "publishing"]
      - .
```

??? warning "EntryPoint-style configuration is deprecated"
    ```yaml
    topic-check:
      enabled: true
      plugins:
        - topic_acl
      publish-acl:
        - username: ["list", "of", "allowed", "topics", "for", "publishing"]
        - .
      acl:
        - username: ["list", "of", "allowed", "topics", "for", "subscribing"]
        - .
    ```

### $SYS topics

`amqtt.plugins.sys.broker.BrokerSysPlugin`

Publishes, on a periodic basis, statistics about the broker

**Configuration**

- `sys_interval` - int, seconds between updates (default: 20)

```yaml
plugins:
  amqtt.plugins.sys.broker.BrokerSysPlugin:
    sys_interval: 20  # int, seconds between updates
```

**Supported Topics**

- `$SYS/broker/version` *(string)*
- `$SYS/broker/load/bytes/received` *(int)*
- `$SYS/broker/load/bytes/sent` *(int)*
- `$SYS/broker/messages/received`  *(int)*
- `$SYS/broker/messages/sent`  *(int)*
- `$SYS/broker/time`  *(int, current time in epoch seconds)*
- `$SYS/broker/uptime` *(int, seconds since broker start)*
- `$SYS/broker/uptime/formatted` *(string, start time of broker in UTC)*
- `$SYS/broker/clients/connected` *(int, number of currently connected clients)*
- `$SYS/broker/clients/disconnected` *(int, number of clients that have disconnected)*
- `$SYS/broker/clients/maximum` *(int, maximum number of clients connected)*
- `$SYS/broker/clients/total` *(int)*
- `$SYS/broker/messages/inflight` *(int)*
- `$SYS/broker/messages/inflight/in` *(int)*
- `$SYS/broker/messages/inflight/out` *(int)*
- `$SYS/broker/messages/inflight/stored` *(int)*
- `$SYS/broker/messages/publish/received` *(int)*
- `$SYS/broker/messages/publish/sent` *(int)*
- `$SYS/broker/messages/retained/count` *(int)*
- `$SYS/broker/messages/subscriptions/count` *(int)*
- `$SYS/broker/heap/size` *(float, MB)*
- `$SYS/broker/heap/maximum` *(float, MB)*
- `$SYS/broker/cpu/percent` *(float, %)*
- `$SYS/broker/cpu/maximum` *(float, %)*


### Event Logger

`amqtt.plugins.logging_amqtt.EventLoggerPlugin`

This plugin issues log messages when [broker and mqtt events](custom_plugins.md#events) are triggered:

- info level messages for `client connected` and `client disconnected`
- debug level for all others

```yaml
plugins:
  amqtt.plugins.logging_amqtt.EventLoggerPlugin:
```


### Packet Logger

`amqtt.plugins.logging_amqtt.PacketLoggerPlugin`

This plugin issues debug-level messages for [mqtt events](custom_plugins.md#client-and-broker): `on_mqtt_packet_sent`
and `on_mqtt_packet_received`.

```yaml
plugins:
  amqtt.plugins.logging_amqtt.PacketLoggerPlugin:
```
