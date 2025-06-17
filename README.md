[![MIT licensed](https://img.shields.io/github/license/Yakifo/amqtt?style=plastic)](https://amqtt.readthedocs.io/en/latest/)
[![CI](https://github.com/Yakifo/amqtt/actions/workflows/ci.yml/badge.svg?branch=rc)](https://github.com/Yakifo/amqtt/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Yakifo/amqtt/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/Yakifo/amqtt/actions/workflows/codeql-analysis.yml)
[![Documentation Status](https://img.shields.io/readthedocs/amqtt?style=plastic&logo=readthedocs)](https://amqtt.readthedocs.io/en/latest/)
[![](https://dcbadge.limes.pink/api/server/https://discord.gg/S3sP6dDaF3?style=plastic)](https://discord.gg/S3sP6dDaF3)
![Python Version](https://img.shields.io/pypi/pyversions/amqtt?style=plastic&logo=python&logoColor=yellow)
![Python Wheel](https://img.shields.io/pypi/wheel/amqtt?style=plastic)
[![PyPI](https://img.shields.io/pypi/v/amqtt?style=plastic&logo=python&logoColor=yellow)](https://pypi.org/project/amqtt/)

![docs/assets/amqtt.svg](https://github.com/Yakifo/amqtt/blob/v0.11.0/docs/assets/amqtt.svg)

`aMQTT` is an open source [MQTT](http://www.mqtt.org) broker and client[^1], natively implemented with Python's [asyncio](https://docs.python.org/3/library/asyncio.html).

## Features

- Full set of [MQTT 3.1.1](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html) protocol specifications
- Communication over TCP and/or websocket, including support for SSL/TLS
- Support QoS 0, QoS 1 and QoS 2 messages flow
- Client auto-reconnection on network lost
- Functionality expansion; plugins included: authentication and `$SYS` topic publishing

## Installation

`amqtt` is available on [PyPI](https://pypi.python.org/pypi/amqtt)

```bash
$ pip install amqtt
```

## Documentation

Available on [Read the Docs](http://amqtt.readthedocs.org/).

## Containerization

Launch from [DockerHub](https://hub.docker.com/repositories/amqtt)

```shell
$ docker run -d -p 1883:1883 amqtt/amqtt:latest
```

## Testing

The `amqtt` project runs a test aMQTT broker/server at [test.amqtt.io](https://test.amqtt.io) which supports: MQTT, MQTT over TLS, websocket, secure websockets.


## Support

Bug reports, patches and suggestions welcome! Just [open an issue](https://github.com/Yakifo/amqtt/issues/new) or join the [discord community](https://discord.gg/S3sP6dDaF3).

## Python Version Compatibility

| Version | hbmqtt compatibility | Supported Python Versions | PyPi Release |
| ------- | -------------------- | ------------------------- | ------------ |
| 0.10.x  | yes [^2]             | 3.7 - 3.9                 | 0.10.1       |
| 0.11.x  | no [^3]              | 3.10 - 3.13               | 0.11.0       |

For a full feature roadmap, see ...

[^1]: Forked from [HBMQTT](https://github.com/beerfactory/hbmqtt) after it was deprecated by the original author.
[^2]: drop-in replacement
[^3]: module renamed and small API differences
