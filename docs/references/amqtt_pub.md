#

::: mkdocs-typer2
    :module: amqtt.scripts.pub_script
    :name: amqtt_pub
    :pretty: true

## Default Configuration

Without the `-c` argument, the client will run with the following, default configuration:

```yaml
--8<-- "../amqtt/amqtt/scripts/default_client.yaml"
```

Using the `-c` argument allows for configuration with a YAML structured file; see [client configuration](client_config.md). 


## Examples

Publish temperature information to localhost with QoS 1:

```bash
amqtt_pub --url mqtt://localhost -t sensors/temperature -m 32 -q 1
```

Publish timestamp and temperature information to a remote host on a non-standard port and QoS 0:

```bash
amqtt_pub --url mqtt://192.168.1.1:1885 -t sensors/temperature -m "1266193804 32"
```

Publish light switch status. Message is set to retained because there may be a long period of time between light switch events:

```bash
amqtt_pub --url mqtt://localhost -r -t switches/kitchen_lights/status -m "on"
```

Send the contents of a file in two ways:

```bash
amqtt_pub --url mqtt://localhost -t my/topic -f ./data

amqtt_pub --url mqtt://localhost -t my/topic -s < ./data
```

Publish temperature information to localhost with QoS 1 over mqtt encapsulated in a websocket connection and additional headers:

```bash
amqtt_pub --url wss://localhost -t sensors/temperature -m 32 -q 1 --extra-headers '{"Authorization": "Bearer <token>"}'
```
