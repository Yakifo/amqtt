# broker

`amqtt` is a command-line script for running a MQTT 3.1.1 broker.

## Usage

`amqtt` usage:

```
amqtt --version
amqtt (-h | --help)
amqtt [-c <config_file> ] [-d]
```

## Options

- `--version` - amqtt version information
- `-h, --help` - Display `amqtt_sub` usage help
- `-c` - Set the YAML configuration file to read and pass to the client runtime.

## Configuration

Without the `-c` argument, the broker will run with the following, default configuration:

```yaml
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
sys_interval: 20
auth:
  allow-anonymous: true
plugins:
  - auth_file
  - auth_anonymous
```

Using the `-c` argument allows for configuration with a YAML structured file. The following sections contain the available configuration elements:

## Field Descriptions

### `listeners`

Defines network listeners for the MQTT server (list).

#### `<interface name>`

`default` for parameters used across all interfaces _or_ name for the specific interface (mapping).

Each entry supports these parameters:

- `bind` (string, _required_)  
  Address and port to bind to, in the form `host:port` (e.g., `0.0.0.0:1883`).

- `type` (string, _required_)  
  Protocol type. Typically `"tcp"` or `"ws"`.

- `max-connections` (integer, _required_)  
  Maximum number of clients that can connect to this interface

- `ssl` (string, _optional, default: `off`_)  
  Disable (`off`) SSL/TLS or enable (`on`) with one of `cafile`, `capath`, `cadata` or `certfile`/`keyfile`.

- `cafile` (string, _optional_)  
  Path to a file of concatenated CA certificates in PEM format. See [Certificates](https://docs.python.org/3/library/ssl.html#ssl-certificates) for more info.

- `capath` (string, _optional_)  
  Path to a directory containing several CA certificates in PEM format, following an [OpenSSL specific layout](https://docs.openssl.org/master/man3/SSL_CTX_load_verify_locations/).

- `cadata` (string, _optional_)  
  Either an ASCII string of one or more PEM-encoded certificates or a bytes-like object of DER-encoded certificates

- `certfile` (string, _optional_)  
  Path to a single file in PEM format containing the certificate as well as any number of CA certificates needed to establish the certificate's authenticity

- `keyfile` (string, _optional_)  
  A file containing the private key. Otherwise the private key will be taken from certfile as well

### timeout-disconnect-delay

Client disconnect timeout without a keep-alive (integer, _optional_)

### plugins

Entry points for optional functionality (_list of strings_); included plugins are:

- `auth_file` – Enables file-based authentication
- `auth_anonymous` – Enables anonymous access
- `event_logger_plugin`
- `packet_logger_plugin`
- `topic_taboo`
- `topic_acl`
- `broker_sys`

### auth

Authentication and authorization settings (mapping).

- `allow-anonymous` (boolean, _optional for `auth_anonymous` plugin_)  
  Allow (`true`) or prevent (`false`) anonymous client to connections.

- `password-file` (string, _required for `auth_file` plugin_)  
  Path to file which includes `username:password` pair, one per line. The password should be encoded using sha-512 with `mkpasswd -m sha-512` or:

```python
import sys
from getpass import getpass
from passlib.hash import sha512_crypt

passwd = input() if not sys.stdin.isatty() else getpass()
print(sha512_crypt.hash(passwd))
```

### sys-interval

Interval in seconds to publish system statistics to `$SYS` topics (integer, _optional for `broker_sys` plugin, defaults to TBD_).

## Configuration example

```yaml
listeners:
  default:
    max-connections: 500
    type: tcp
  my-tcp-1:
    bind: 127.0.0.1:1883
  my-tcp-2:
    bind: 1.2.3.4:1883
    max-connections: 1000
  my-tcp-tls-1:
    bind: 127.0.0.1:8883
    ssl: on
    cafile: /some/cafile
  my-ws-1:
    bind: 0.0.0.0:9001
    type: ws
  my-wss-1:
    bind: 0.0.0.0:9003
    type: ws
    ssl: on
    certfile: /some/certfile
    keyfile: /some/key
plugins:
  - auth_file
  - broker_sys

timeout-disconnect-delay: 2
auth:
  password-file: /some/passwd_file
```

The `listeners` section defines 5 bindings:

- `my-tcp-1`: an unsecured TCP listener on port 1883 allowing `500` clients connections simultaneously
- `my-tcp-2`: an unsecured TCP listener on port 1884 allowing `1000` client connections
- `my-tcp-ssl-1`: a secured TCP listener on port 8883 allowing `500` clients connections simultaneously
- `my-ws-1`: an unsecured websocket listener on port 9001 allowing `500` clients connections simultaneously
- `my-wss-1`: a secured websocket listener on port 9003 allowing `500`

The plugins section enables:

- `auth_file` plugin, requiring `password-file` to be defined in the `auth` section
- `broker_sys` plugin, requiring `sys_interval` to be defined

Authentication allows anonymous logins and password file based authentication. Password files are required to be text files containing user name and password in the form of:

```
username:password
```

where `password` should be the encrypted password. Use the `mkpasswd -m sha-512` command to build encoded passphrase. Password file example:

```
# Test user with 'test' password encrypted with sha-512
test:$6$l4zQEHEcowc1Pnv4$HHrh8xnsZoLItQ8BmpFHM4r6q5UqK3DnXp2GaTm5zp5buQ7NheY3Xt9f6godVKbEtA.hOC7IEDwnok3pbAOip.
```
