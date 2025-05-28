# amqtt_pub

`amqtt_pub` is a MQTT client that publishes simple messages on a topic from the command line.

## Usage

`amqtt_pub` usage:

```
amqtt_pub --version
amqtt_pub (-h | --help)
amqtt_pub --url BROKER_URL -t TOPIC (-f FILE | -l | -m MESSAGE | -n | -s) [-c CONFIG_FILE] [-i CLIENT_ID] [-d]
           [-q | --qos QOS] [-d] [-k KEEP_ALIVE] [--clean-session]
           [--ca-file CAFILE] [--ca-path CAPATH] [--ca-data CADATA]
           [ --will-topic WILL_TOPIC [--will-message WILL_MESSAGE] [--will-qos WILL_QOS] [--will-retain] ]
           [--extra-headers HEADER]
```

Note that for simplicity, `amqtt_pub` uses mostly the same argument syntax as [mosquitto_pub](http://mosquitto.org/man/mosquitto_pub-1.html).

## Options

- `--version` - amqtt version information
- `-h, --help` - Display `amqtt_pub` usage help
- `-c` - Set the YAML configuration file to read and pass to the client runtime.
- `-d` - Enable debugging information.
- `--ca-file` - Define the path to a file containing PEM encoded CA certificates that are trusted. Used to enable SSL communication.
- `--ca-path` - Define the path to a directory containing PEM encoded CA certificates that are trusted. Used to enable SSL communication.
- `--ca-data` - Set the PEM encoded CA certificates that are trusted. Used to enable SSL communication.
- `--clean-session` - If given, set the CONNECT clean session flag to True.
- `-f` - Send the contents of a file as the message. The file is read line by line, and `amqtt_pub` will publish a message for each line read.
- `-i` - The id to use for this client. If not given, defaults to `amqtt_pub/` appended with the process id and the hostname of the client.
- `-l` - Send messages read from stdin. `amqtt_pub` will publish a message for each line read. Blank lines won't be sent.
- `-k` - Set the CONNECT keep alive timeout.
- `-m` - Send a single message from the command line.
- `-n` - Send a null (zero length) message.
- `-q, --qos` - Specify the quality of service to use for the message, from 0, 1 and 2. Defaults to 0.
- `-s` - Send a message read from stdin, sending the entire content as a single message.
- `-t` - The MQTT topic on which to publish the message.
- `--url` - Broker connection URL, conforming to [MQTT URL scheme](https://github.com/mqtt/mqtt.github.io/wiki/URI-Scheme).
- `--will-topic` - The topic on which to send a Will, in the event that the client disconnects unexpectedly.
- `--will-message` - Specify a message that will be stored by the broker and sent out if this client disconnects unexpectedly. This must be used in conjunction with `--will-topic`.
- `--will-qos` - The QoS to use for the Will. Defaults to 0. This must be used in conjunction with `--will-topic`.
- `--will-retain` - If given, if the client disconnects unexpectedly the message sent out will be treated as a retained message. This must be used in conjunction with `--will-topic`.
- `--extra-headers` - Specify a JSON object string with key-value pairs representing additional headers that are transmitted on the initial connection, but only when using a websocket connection

## Default Configuration

Without the `-c` argument, the broker will run with the following, default configuration:

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
