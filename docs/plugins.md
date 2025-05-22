# Existing Plugins

## Plugin: Anonymous Authentication

plugin which allows clients to connect without credentials

### Config Options

```yaml

auth:
  allow-anonymous: true # or false

```

## Plugin: Password Authentication from File

clients are authorized by providing username and password, compared against file

### Config Options

```yaml

auth:
  password-file: /path/to/password_file

```

### File Format

  
The file includes `username:password` pairs, one per line.

The password should be encoded using sha-512 with `mkpasswd -m sha-512` or:

```python
import sys
from getpass import getpass
from passlib.hash import sha512_crypt

passwd = input() if not sys.stdin.isatty() else getpass()
print(sha512_crypt.hash(passwd))
```
## Plugin: $SYS

Publishes, on a periodic basis, statistics about the broker

### Config Options

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
