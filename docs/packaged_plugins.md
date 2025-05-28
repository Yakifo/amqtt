# Existing Plugins

With the aMQTT Broker plugins framework, one can add additional functionality without
having to rewrite core logic. The list of plugins that get loaded are specified in `pyproject.toml`;
each plugin can then check the configuration to determine how to behave (including disabling).

```toml
[project.entry-points."amqtt.broker.plugins"]
plugin_alias = "module.submodule.file:ClassName"
```

## auth_anonymous (Auth Plugin)

`amqtt.plugins.authentication:AnonymousAuthPlugin`


**Config Options**

```yaml
auth:
  plugins:
    - auth_anonymous
  allow-anonymous: true # if false, providing a username will allow access

```

!!! danger
    even if `allow-anonymous` is set to `false`, the plugin will still allow access if a username is provided by the client


## auth_file (Auth Plugin)

`amqtt.plugins.authentication:FileAuthPlugin`

clients are authorized by providing username and password, compared against file

**Config Options**

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

## Taboo (Topic Plugin)

`amqtt.plugins.topic_checking:TopicTabooPlugin`


Prevents using topics named: `prohibited`, `top-secret`, and `data/classified`

**Configuration**

```yaml
topic-check:
  enabled: true
  plugins:
    - topic_taboo
```

## ACL (Topic Plugin)

`amqtt.plugins.topic_checking:TopicAccessControlListPlugin`

**Configuration**

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






## Plugin: $SYS

Publishes, on a periodic basis, statistics about the broker

**Config Options**

- `sys_interval` - int, seconds between updates

### Supported Topics

- `$SYS/broker/load/bytes/received` - payload: 'data` - payload: `data`,  int
- `$SYS/broker/load/bytes/sent` - payload: 'data` - payload: `data`,  int
- `$SYS/broker/messages/received` - payload: `data`, int
- `$SYS/broker/messages/sent` - payload: `data`, int
- `$SYS/broker/time` - payload: `data`,  int (current time, epoch seconds)
- `$SYS/broker/uptime` - payload: `data`, int (seconds since broker start)
- `$SYS/broker/uptime/formatted` - payload: `data`, datetime (start time of broker in UTC)
- `$SYS/broker/clients/connected` - payload: `data`, int
- `$SYS/broker/clients/disconnected` - payload: `data`, int
- `$SYS/broker/clients/maximum` - payload: `data`, int
- `$SYS/broker/clients/total` - payload: `data`, int
- `$SYS/broker/messages/inflight` - payload: `data`, int
- `$SYS/broker/messages/inflight/in` - payload: `data`, int
- `$SYS/broker/messages/inflight/out` - payload: `data`, int
- `$SYS/broker/messages/inflight/stored` - payload: `data`, int
- `$SYS/broker/messages/publish/received` - payload: `data`, int
- `$SYS/broker/messages/publish/sent` - payload: `data`, int
- `$SYS/broker/messages/retained/count` - payload: `data`, int
- `$SYS/broker/messages/subscriptions/count` - payload: `data`, int
