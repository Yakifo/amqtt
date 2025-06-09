[![MIT licensed](https://img.shields.io/github/license/Yakifo/amqtt?style=flat-square)](https://amqtt.readthedocs.io/en/latest/)
[![CI](https://github.com/Yakifo/amqtt/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Yakifo/amqtt/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Yakifo/amqtt/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/Yakifo/amqtt/actions/workflows/codeql-analysis.yml)
[![Documentation Status](https://img.shields.io/readthedocs/amqtt?style=flat-square)](https://amqtt.readthedocs.io/en/latest/)
[![Join the chat](https://img.shields.io/gitter/room/Yakifo/amqtt?style=flat-square)](https://gitter.im/amqtt/community)
![Python Version](https://img.shields.io/pypi/pyversions/amqtt?style=flat-square)
![Python Wheel](https://img.shields.io/pypi/wheel/amqtt?style=flat-square)
[![PyPI](https://img.shields.io/pypi/v/amqtt?style=flat-square)](https://pypi.org/project/amqtt/)

![docs/assets/amqtt.svg](docs/assets/amqtt.svg)

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

## Containerization

Launch from [DockerHub](https://hub.docker.com/repository/docker/amqtt/amqtt)

```shell
$ docker run -d -p 1883:1883 amqtt/amqtt:latest
```

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
