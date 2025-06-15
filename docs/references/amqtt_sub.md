#

::: mkdocs-typer2
    :module: amqtt.scripts.sub_script
    :name: amqtt_pub
    :pretty: true

## Default Configuration

Without the `-c` argument, the client will run with the following, default configuration:

```yaml
--8<-- "amqtt/scripts/default_client.yaml"
```

Using the `-c` argument allows for configuration with a YAML structured file; see [client configuration](client_config.md). 


## Examples

Subscribe with QoS 0 to all messages published under $SYS/:

```bash
amqtt_sub --url mqtt://localhost -t '$SYS/#' -q 0
```

Subscribe to 10 messages with QoS 2 from /#:

```bash
amqtt_sub --url mqtt://localhost -t # -q 2 -n 10
```

Subscribe with QoS 0 to all messages published under $SYS/ over mqtt encapsulated in a websocket connection and additional headers:

```bash
amqtt_sub --url wss://localhost -t '$SYS/#' -q 0 --extra-headers '{"Authorization": "Bearer <token>"}'
```
