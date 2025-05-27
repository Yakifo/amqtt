
![assets/amqtt.svg](assets/amqtt.svg)

`aMQTT` is an open source [MQTT](http://www.mqtt.org) broker[^1], natively implemented with Python's [asyncio](https://docs.python.org/3/library/asyncio.html).

## Features

- Full set of [MQTT 3.1.1](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html) protocol specifications
- Communication over TCP and/or websocket, including support for SSL/TLS
- Support QoS 0, QoS 1 and QoS 2 messages flow
- Client auto-reconnection on network lost
- Functionality expansion; plugins included:
  - Authentication through password file
  - Basic `$SYS` topics

## Installation

`amqtt` is available on [PyPI](https://pypi.python.org/pypi/amqtt)

```bash
$ pip install amqtt
```

## Documentation

Available on [Read the Docs](http://amqtt.readthedocs.org/).

## Support

Bug reports, patches and suggestions welcome! Just [open an issue](https://github.com/Yakifo/amqtt/issues/new) or join the [gitter community](https://gitter.im/amqtt/community).

## Python Version Compatibility

| Version | hbmqtt compatibility | Supported Python Versions | PyPi Release |
| ------- | -------------------- | ------------------------- | ------------ |
| 0.10.x  | yes [^2]             | 3.7 - 3.9                 | 0.10.1       |
| 0.11.x  | no [^3]              | 3.10 - 3.13               | 0.11.0       |

For a full feature roadmap, see ...

[^1]: Forked from [HBMQTT](https://github.com/beerfactory/hbmqtt) after it was deprecated by the original author.
[^2]: drop-in replacement
[^3]: module renamed and small API differences
