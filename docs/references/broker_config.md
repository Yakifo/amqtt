# Broker Configuration

This configuration structure is valid as a python dictionary passed to the `amqtt.broker.Broker` class's `__init__` method or
as a yaml formatted file passed to the `amqtt` script.

### `listeners` *(list[dict[str, Any]])*

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

### `timeout-disconnect-delay` *(int)*

Client disconnect timeout without a keep-alive


### `plugins` *(mapping)*

A list of strings representing the modules and class name of `BasePlugin`, `BaseAuthPlugin` and `BaseTopicPlugins`. Each
entry may have one or more configuration settings. For more information, see the [configuration of the included plugins](../packaged_plugins.md)


??? warning "Deprecated: `sys_interval` "
    **`sys_interval`** *(int)*
    
    System status report interval in seconds, used by the `amqtt.plugins.sys.broker.BrokerSysPlugin`.




??? warning "Deprecated: `auth` configuration settings"

    **`auth`**
    
    Configuration for authentication behaviour:
      
    - `plugins` *(list[string])*: defines the list of plugins which are activated as authentication plugins.
    
    !!! note
        Plugins used here must first be defined in the `amqtt.broker.plugins` [entry point](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata).
          

    !!! warning
        If `plugins` is omitted from the `auth` section, all plugins listed in the `amqtt.broker.plugins` entrypoint will be enabled
                  for authentication, including _allowing anonymous login._
          
      `plugins: []` will deny connections from all clients.
          
    - `allow-anonymous` *(bool)*: `True` will allow anonymous connections, used by `amqtt.plugins.authentication.AnonymousAuthPlugin`. 
          
    !!! danger
        `False` does not disable the `auth_anonymous` plugin; connections will still be allowed as long as a username is provided. If security is required, do not include `auth_anonymous` in the `plugins` list.
      

    - `password-file` *(string)*. Path to sha-512 encoded password file, used by `amqtt.plugins.authentication.FileAuthPlugin`.

??? warning "Deprecated: `topic-check` configuration settings"


    **`topic-check`**
    
    Configuration for access control policies for publishing and subscribing to topics:
    
    - `enabled` *(bool)*: Enable access control policies (`true`). `false` will allow clients to publish and subscribe to any topic.
      - `plugins` *(list[string])*: defines the list of plugins which are activated as access control plugins. Note the plugins must be defined in the `amqtt.broker.plugins` [entry point](https://pythonhosted.org/setuptools/setuptools.html#dynamic-discovery-of-services-and-plugins).
    
      - `acl` *(list)*: plugin to determine subscription access; if `publish-acl` is not specified, determine both publish and subscription access.
         The list should be a key-value pair, where:
      `<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).
    
          *used by the `amqtt.plugins.topic_acl.TopicAclPlugin`*

      - `publish-acl` *(list)*: plugin to determine publish access. This parameter defines the list of access control rules; each item is a key-value pair, where:
      `<username>:[<topic1>, <topic2>, ...]` *(string, list[string])*: username of the client followed by a list of allowed topics (wildcards are supported: `#`, `+`).
      
      _Reserved usernames (used by the `amqtt.plugins.topic_acl.TopicAclPlugin`)_
      
              - The username `admin` is allowed access to all topic.
              - The username `anonymous` will control allowed topics if using the `auth_anonymous` plugin.
      
      
       



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
plugins:
  - amqtt.plugins.authentication.AnonymousAuthPlugin:
      allow-anonymous: true
  - amqtt.plugin.authentication.FileAuthPlugin:
      password-file: /some/password-file
  - amqtt.plugins.topic_checking.TopicAccessControlListPlugin:
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
