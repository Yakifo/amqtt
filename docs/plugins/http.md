# Authentication & Authorization via external HTTP server

`amqtt.contrib.http.HttpAuthPlugin`

If clients accessing the broker are managed by another application, it can implement API endpoints
that respond with information about client authenticated and topic-level authorization.

!!! info "browser-based mqtt over websockets"

    One of the primary use cases for this plugin is to enable browser-based applications to communicate with mqtt
    over websockets.

    !!! warning
        Care must be taken to make sure the mqtt password is secure (encrypted).
    
    For more implementation information:

    ??? info "recipe for authentication"
        Provide the client id and username when webpage is initially rendered or passed to the mqtt initialization from stored
         cookies. If application is secure, the user's password will already be stored as a hashed value and, therefore, cannot
         be used in this context to  authenticate a client. Instead, the application should create its own encrypted key (eg jwt)
         which the server can then verify when the broker contacts the application.

    ??? example "mqtt in javascript"
          Example initialization of mqtt in javascript:

            import mqtt from 'mqtt';
            const url = 'https://path.to.amqtt.broker';
            const options = {
              'myclientid',
              connectTimeout: 30000,
              username: 'myclientid',
              password: ''  // encrypted password
            };
            try {
              const clientMqtt = await mqtt.connect(url, options);

See the [Request and Response Modes](#request-response-modes) section below for details on `params_mode` and `response_mode`. 

::: amqtt.contrib.http.HttpAuthPlugin.Config
    options:
      show_source: false
      heading_level: 4
      extra:
        class_style: "simple"

[//]: # (manually creating the heading so it doesn't show in the sidebar ToC)
[](){#request-response-modes}
<h2>Request and Response Modes</h2>

Each URI endpoint will receive different information in order to determine authentication and authorization;
format will depend on `params_mode` configuration attribute (`json` or `form`).:

*For user authentication, the request will contain:*

    - username *(str)*
    - password *(str)*
    - client_id *(str)*

*For superuser validation, the request will contain:*

    - username *(str)*

*For acl check, the request will contain:*

    - username *(str)*
    - client_id *(str)*
    - topic *(str)*
    - acc *(int)* : client can receive (1), can publish(2), can receive & publish (3) and can subscribe (4)

All endpoints should respond with the following, dependent on `response_mode` configuration attribute:

*In `status` mode:*

    - status code: 2xx (granted) or 4xx(denied) or 5xx (noop)

!!! note "5xx response"
    **noop** (no operation): plugin will not participate in the filtering operation and will defer to another
    topic filtering plugin to determine access. if there is no other topic filtering plugin, access will be denied.

*In `json` mode:*

    - status code: 2xx
    - content-type: application/json
    - response: {'ok': True } (granted)
                or {'ok': False, 'error': 'optional error message' } (denied)
                or { 'error': 'optional error message' } (noop)

!!! note "excluded 'ok' key"
    **noop** (no operation): plugin will not participate in the filtering operation and will defer to another
     topic filtering plugin to determine access. if there is no other topic filtering plugin, access will be denied.

*In `text` mode:*

    - status code: 2xx
    - content-type: text/plain
    - response: 'ok' or 'error'

!!! note "noop not supported"
    in text mode, noop (no operation) is not supported