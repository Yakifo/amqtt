# Quickstart

`aMQTT` is an open source `MQTT` client and broker implementation; these can be integrated into other projects using the appropriate APIs. To get started, three command-line scripts are also installed along with the package:

- `amqtt` - the MQTT broker
- `amqtt_pub` - an MQTT client to publish messages
- `amqtt_sub` - an MQTT client to listen for messages

To install the `aMQTT` package:

```bash
(venv) $ pip install amqtt
```

## Running a broker

`amqtt` is a command-line tool for the MQTT 3.1.1 compliant broker:

```bash
$ amqtt
[2015-11-06 22:45:16,470] :: INFO - Listener 'default' bind to 0.0.0.0:1883 (max_connections=-1)
```

See [amqtt reference documentation](references/amqtt.md) for details about available options and settings.

## Publishing messages

`amqtt_pub` is a command-line tool which can be used for publishing some messages on a topic. It requires a few arguments like broker URL, topic name, QoS and data to send. Additional options allow more complex use case.

Publishing `some_data` to as `/test` topic using a TCP connection to `test.mosquitto.org`:

```bash
$ amqtt_pub --url mqtt://test.mosquitto.org -t test -m some_data
[2015-11-06 22:21:55,108] :: INFO - amqtt_pub/5135-myhostname.local Connecting to broker
[2015-11-06 22:21:55,333] :: INFO - amqtt_pub/5135-myhostname.local Publishing to 'test'
[2015-11-06 22:21:55,336] :: INFO - amqtt_pub/5135-myhostname.local Disconnected from broker
```

Websocket connections are also supported:

```bash
$ amqtt_pub --url ws://test.mosquitto.org:8080 -t test -m some_data
[2015-11-06 22:22:42,542] :: INFO - amqtt_pub/5157-myhostname.local Connecting to broker
[2015-11-06 22:22:42,924] :: INFO - amqtt_pub/5157-myhostname.local Publishing to 'test'
[2015-11-06 22:22:52,926] :: INFO - amqtt_pub/5157-myhostname.local Disconnected from broker
```

Additionally, TCP connections can be secured via TLS and websockets via SSL.

`amqtt_pub` can read from file or stdin and use data read as message payload:

```bash
$ some_command | amqtt_pub --url mqtt://localhost -t test -l
```

See [amqtt_pub reference documentation](references/amqtt_pub.md) for details about available options and settings.

## Subscribing a topic

`amqtt_sub` is a command-line tool which can be used to subscribe to a specific topics or a topic patterns.

Subscribe to the `my/test` topic and the `test/#` topic pattern:

```bash
$ amqtt_sub --url mqtt://localhost -t my/test -t test/#
```

This will run and print messages to standard output; it can be stopped by ^C.

See [amqtt_sub reference documentation](references/amqtt_sub.md) for details about available options and settings.

## URL Scheme

aMQTT command line tools use the `--url` to establish a network connection with the broker. It follows Python's [urlparse](https://docs.python.org/3/library/urllib.parse.html) structure but also adds the [mqtt scheme](https://github.com/mqtt/mqtt.org/wiki/URI-Scheme).

```
[mqtt|ws][s]://[username][:password]@host.domain[:port]
```

Here are some examples:

```
mqtt://localhost
mqtt://localhost:1884
mqtt://user:password@localhost
ws://test.mosquitto.org
wss://user:password@localhost
```
