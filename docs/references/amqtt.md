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
--8<-- "../amqtt/amqtt/scripts/default_broker.yaml"
```

Using the `-c` argument allows for configuration with a YAML structured file; see [broker configuration](broker_config.md). 
