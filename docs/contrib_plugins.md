# Contributed Plugins

Beyond the original set of plugins created for aMQTT, `amqtt.contrib` plugins have been
more recently developed and contributed to the amqtt code base. These plugins require extra
dependencies:

`pip install amqtt[contrib]`

### Session Persistence

`amqtt.plugins.persistence.SessionDBPlugin`

Plugin to store session information and retained topic messages in the event that the broker terminates abnormally.

This plugin requires additional dependencies:

**Configuration**

- `file` - *(string)* path & filename to store the session db. default: `amqtt.db`
- `clear_on_shutdown` *(bool)* if the broker shutdowns down normally, don't retain any information. default: `True`

```yaml
plugins:
  amqtt.plugins.persistence.SessionDBPlugin:
    file: 'amqtt.db'
    clear_on_shutdown: True
```

## Authentication & Topic Access via external HTTP server

`amqtt.contrib.http.HttpAuthTopicPlugin`

If clients accessing the broker are managed by another application, implement API endpoints
that allows the broker to check if a client is authenticated and what topics that client
is authorized to access.

**Configuration**

- `host` *(str) hostname of the server for the auth & acl check
- `port` *(int) port of the server for the auth & acl check
- `user_uri` *(str) uri of the user auth check (e.g. '/user')
- `topic_uri` *(str) uri of the topic check (e.g. '/acl')
- `request_method` *(RequestMethod) send the request as a GET, POST or PUT
- `params_mode` *(ParamsMode) send the request with json or form data
- `response_mode` *(ResponseMode) expected response from the auth/acl server. STATUS (code), JSON, or TEXT.
- `user_agent` *(str) the 'User-Agent' header sent along with the request

Each endpoint (uri) will receive the information needed to determine authentication and authorization (in either
json or form data format, based on the `params_mode`)

For user authentication (`user_uri`), the http server will receive in json or form format the following:
    - username *(str)*
    - password *(str)*
    - client_id *(str)*

For superuser validation (`superuser_uri`), the http server will receive in json or form format the following:
    - username *(str)*

For acl check (`acl_uri`), the http server will receive in json or form format the following:
    - username *(str)*
    - client_id *(str)*
    - topic *(str)*
    - acc *(int)* client can receive (1), can publish(2), can receive & publish (3) and can subscribe (4)


The HTTP endpoints can respond in three different ways, depending on `response_mode`:

1. STATUS - allowing access should respond with a 2xx status code. rejection is 4xx. 
    if a 5xx is received, the plugin will not participate in the filtering operation and will defer to another topic filtering plugin to determine access
2. JSON - response should be `{'ok':true|false|null, 'error':'optional reason for false or null response'}`.
   `true` allows access, `false` denies access and `null` the plugin will not participate in the filtering operation
3. TEXT - `ok` allows access, any other message denies access. non-participation not supported with this mode.
