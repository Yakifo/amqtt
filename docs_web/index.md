# Home

![assets/amqtt.svg](assets/amqtt.svg)

`aMQTT` is an open source [MQTT](http://www.mqtt.org) broker and client, natively implemented with Python's [asyncio](https://docs.python.org/3/library/asyncio.html).

## Features

- Full set of [MQTT 3.1.1](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html) protocol specifications
- Communication over TCP and/or websocket, including support for SSL/TLS
- Support QoS 0, QoS 1 and QoS 2 messages flow
- Client auto-reconnection on network lost
- Functionality expansion; plugins included: authentication and `$SYS` topic publishing

## Installation

`amqtt` is available on ![pypi](assets/python.svg) [PyPI](https://pypi.python.org/pypi/amqtt)

## Documentation

`amqtt` docs are available on ![readthedocs](assets/readthedocs.svg) [Read the Docs](http://amqtt.readthedocs.org/).

## Containerization

Launch from ![dockerhub](assets/docker.svg) [DockerHub](https://hub.docker.com/repositories/amqtt)

```shell
$ docker run -d -p 1883:1883 amqtt/amqtt:latest
```

## Testing

The `amqtt` project runs a test aMQTT broker/server at [test.amqtt.io](https://test.amqtt.io) which supports: MQTT, MQTT over TLS, websocket, secure websockets.


## Support

`amqtt` development is available on ![github](assets/github.svg) [GitHub](https://github.com/Yakifo/amqtt). Bug reports, patches and suggestions welcome!

![github](assets/github.svg) [Open an issue](https://github.com/Yakifo/amqtt/issues/new) or join the ![discord](assets/discord.svg) [discord community](https://discord.gg/S3sP6dDaF3).

