# Broker Configuration

This configuration structure is valid as a python dictionary passed to the `amqtt.broker.Broker` class's `__init__` method or
as a yaml formatted file passed to the `amqtt` script.

### `listeners` *(list[mapping])*

Defines the network listeners used by the service. Items defined in the `default` listener will be
applied to all other listeners, unless they are overridden by the configuration for the specific
listener.

- `default` | `<listener_name>`: Named listener
    - `type` *(string)*: Transport type. Can be `tcp` or `ws`.
    - `bind` *(string)*: IP address and port (e.g., `0.0.0.0:1883`)
    - `max-connections` *(integer)*: Maximum number of clients that can connect to this interface
    - `ssl` *(string)*: Enable SSL connection. Can be `on` or `off` (default: off).
    - `cafile` *(string)*:  Path to a file of concatenated CA certificates in PEM format. See [Certificates](https://docs.python.org/3/library/ssl.html#ssl-certificates) for more info.
    - `capath` *(string)*:  Path to a directory containing several CA certificates in PEM format, following an [OpenSSL specific layout](https://docs.openssl.org/master/man3/SSL_CTX_load_verify_locations/).
    - `cadata` *(string)*:    Either an ASCII string of one or more PEM-encoded certificates or a bytes-like object of DER-encoded certificates.
    - `certfile` *(string)*: Path to a single file in PEM format containing the certificate as well as any number of CA certificates needed to establish the certificate's authenticity.
    - `keyfile` *(string): A file containing the private key. Otherwise the private key will be taken from `certfile` as well.

### `sys_interval` *(int)*

System status report interval in seconds (`broker_sys` plugin)

### `timeout-disconnect-delay` *(int)*

Client disconnect timeout without a keep-alive. 

### `auth` *(mapping)*

Configuration for authentication behaviour:

- `plugins` *(list[string])*: defines the list of plugins which are activated as authentication plugins.

    !!! note "Entry points"
        Plugins used here must first be defined in the `amqtt.broker.plugins` [entry point](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata).


    !!! danger "Legacy behavior"
        if `plugins` is omitted from the `auth` section, all plugins listed in the `amqtt.broker.plugins` entrypoint will be enabled
        for authentication, *including allowing anonymous login.*

        `plugins: []` will deny connections from all clients.

- `allow-anonymous` *(bool)*: `True` will allow anonymous connections.

      *Used by the internal `amqtt.plugins.authentication.AnonymousAuthPlugin` plugin* 
    
    !!! danger "Username only connections"
          `False` does not disable the `auth_anonymous` plugin; connections will still be allowed as long as a username is provided.

           If security is required, do not include `auth_anonymous` in the `plugins` list.



- `password-file` *(string)*: Path to file which includes `username:password` pair, one per line. The password should be encoded using sha-512 with `mkpasswd -m sha-512` or:
  ```python
  import sys
  from getpass import getpass
  from passlib.hash import sha512_crypt
  
  passwd = input() if not sys.stdin.isatty() else getpass()
  print(sha512_crypt.hash(passwd))
  ```
  
      *Used by the internal `amqtt.plugins.authentication.FileAuthPlugin` plugin.*

### `topic-check` *(mapping)*

Configuration for access control policies for publishing and subscribing to topics:

- `enabled` *(bool)*: Enable access control policies (`true`). `false` will allow clients to publish and subscribe to any topic.
- `plugins` *(list[string])*: defines the list of plugins which are activated as access control plugins. Note the plugins must be defined in the `amqtt.broker.plugins` [entry point](https://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins).

- `acl` *(list)*: plugin to determine subscription access; if `publish-acl` is not specified, determine both publish and subscription access.
   The list should be a key-value pair, where:
`<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).

    *used by the `amqtt.plugins.topic_acl.TopicAclPlugin`*

- `publish-acl` *(list)*: plugin to determine publish access. This parameter defines the list of access control rules; each item is a key-value pair, where:
`<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).

    !!! info "Reserved usernames"

        - The username `admin` is allowed access to all topic.
        - The username `anonymous` will control allowed topics if using the `auth_anonymous` plugin.


    *used by the `amqtt.plugins.topic_acl.TopicAclPlugin`*



## Default Configuration

```yaml
--8<-- "amqtt/scripts/default_broker.yaml"
```

## Example
  
```yaml
listeners:
    default:
        max-connections: 500
        type: tcp
    my-tcp-1:
        bind: 127.0.0.1:1883
    my-tcp-2:
        bind: 1.2.3.4:1884
        max-connections: 1000
    my-tcp-ssl-1:
        bind: 127.0.0.1:8885
        ssl: on
        cafile: /some/cafile
        capath: /some/folder
        capath: certificate data
        certfile: /some/certfile
        keyfile: /some/key
    my-ws-1:
        bind: 0.0.0.0:8080
        type: ws
    my-wss-1:
        bind: 0.0.0.0:9003
        type: ws
        ssl: on
        certfile: /some/certfile
        keyfile: /some/key
timeout-disconnect-delay: 2
auth:
    plugins: ['auth_anonymous', 'auth_file']
    allow-anonymous: true
    password-file: /some/password-file
topic-check:
    enabled: true
    plugins: ['topic_acl']
    acl:
        username1: ['repositories/+/master', 'calendar/#', 'data/memes']
        username2: [ 'calendar/2025/#', 'data/memes']
        anonymous: ['calendar/2025/#']
```

This configuration file would create the following listeners:

- `my-tcp-1`: an unsecured TCP listener on port 1883 allowing `500` clients connections simultaneously
- `my-tcp-2`: an unsecured TCP listener on port 1884 allowing `1000` client connections
- `my-tcp-ssl-1`: a secured TCP listener on port 8883 allowing `500` clients connections simultaneously
- `my-ws-1`: an unsecured websocket listener on port 9001 allowing `500` clients connections simultaneously
- `my-wss-1`: a secured websocket listener on port 9003 allowing `500`

And enable the following access controls:

- `username1` to login and subscribe/publish to topics `repositories/+/master`, `calendar/#` and `data/memes`
- `username2` to login and subscribe/publish to topics `calendar/2025/#` and `data/memes`
- any user not providing credentials (`anonymous`) can only subscribe/publish to `calendar/2025/#`
