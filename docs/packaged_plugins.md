# Existing Plugins

With the aMQTT Broker plugins framework, one can add additional functionality without
having to rewrite core logic. Plugins loaded by default are specified in `pyproject.toml`:

```yaml
--8<-- "pyproject.toml:included"
```

## auth_anonymous (Auth Plugin)

`amqtt.plugins.authentication:AnonymousAuthPlugin`


**Configuration**

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

**Configuration**

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

- `acl` *(list)*: determines subscription access; if `publish-acl` is not specified, determine both publish and subscription access.
   The list should be a key-value pair, where:
`<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).


- `publish-acl` *(list)*: determines publish access. This parameter defines the list of access control rules; each item is a key-value pair, where:
`<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).

    !!! info "Reserved usernames"

        - The username `admin` is allowed access to all topics.
        - The username `anonymous` will control allowed topics, if using the `auth_anonymous` plugin.

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

`amqtt.plugins.sys.broker:BrokerSysPlugin`

Publishes, on a periodic basis, statistics about the broker

**Configuration**

- `sys_interval` - int, seconds between updates

**Supported Topics**

- `$SYS/broker/version` - payload: `str`
- `$SYS/broker/load/bytes/received` - payload: `int`
- `$SYS/broker/load/bytes/sent` - payload: `int`
- `$SYS/broker/messages/received` - payload: `int`
- `$SYS/broker/messages/sent` - payload: `int`
- `$SYS/broker/time` - payload: `int` (current time, epoch seconds)
- `$SYS/broker/uptime` - payload: `int` (seconds since broker start)
- `$SYS/broker/uptime/formatted` - payload: `str` (start time of broker in UTC)
- `$SYS/broker/clients/connected` - payload: `int` (current number of connected clients)
- `$SYS/broker/clients/disconnected` - payload: `int` (number of clients that have disconnected)
- `$SYS/broker/clients/maximum` - payload: `int`
- `$SYS/broker/clients/total` - payload: `int`
- `$SYS/broker/messages/inflight` - payload: `int`
- `$SYS/broker/messages/inflight/in` - payload: `int`
- `$SYS/broker/messages/inflight/out` - payload: `int`
- `$SYS/broker/messages/inflight/stored` - payload: `int`
- `$SYS/broker/messages/publish/received` - payload: `int`
- `$SYS/broker/messages/publish/sent` - payload: `int`
- `$SYS/broker/messages/retained/count` - payload: `int`
- `$SYS/broker/messages/subscriptions/count` - payload: `int`
