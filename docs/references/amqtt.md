#

::: mkdocs-typer2
    :module: amqtt.scripts.broker_script
    :name: amqtt
    :pretty: true

## Configuration

Without the `-c` argument, the broker will run with the following, default configuration:

```yaml
--8<-- "amqtt/scripts/default_broker.yaml"
```

Using the `-c` argument allows for configuration with a YAML structured file; see [broker configuration](broker_config.md). 
