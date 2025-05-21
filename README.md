[![MIT licensed](https://img.shields.io/github/license/Yakifo/amqtt?style=flat-square)](https://amqtt.readthedocs.io/en/latest/)
[![CI](https://img.shields.io/github/workflow/status/Yakifo/amqtt/Python%20package?style=flat-square)](https://github.com/Yakifo/amqtt/actions/workflows/python-package.yml)
[![Coverage](https://img.shields.io/coveralls/github/Yakifo/amqtt?style=flat-square)](https://coveralls.io/github/Yakifo/amqtt?branch=master)
[![Documentation Status](https://img.shields.io/readthedocs/amqtt?style=flat-square)](https://amqtt.readthedocs.io/en/latest/)
[![Join the chat](https://img.shields.io/gitter/room/Yakifo/amqtt?style=flat-square)](https://gitter.im/amqtt/community)
![Python Version](https://img.shields.io/pypi/pyversions/amqtt?style=flat-square)
![Python Wheel](https://img.shields.io/pypi/wheel/amqtt?style=flat-square)
[![PyPI](https://img.shields.io/pypi/v/amqtt?style=flat-square)](https://pypi.org/project/amqtt/)

# WORK IN PROGRESS
[!!! MAINTAINERS WANTED !!!](https://github.com/Yakifo/amqtt/issues/163)

# aMQTT

`aMQTT` is an open source [MQTT](http://www.mqtt.org) client and broker implementation.

Built on top of [asyncio](https://docs.python.org/3/library/asyncio.html), Python's standard asynchronous I/O framework, aMQTT provides a straightforward API based on coroutines, making it easy to write highly concurrent applications.

It was forked from [HBMQTT](https://github.com/beerfactory/hbmqtt) after it was deprecated by the original author.

## Features

aMQTT implements the full set of [MQTT 3.1.1](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html) protocol specifications and provides the following features:

- Support QoS 0, QoS 1 and QoS 2 messages flow
- Client auto-reconnection on network lost
- Authentication through password file (more methods can be added through a plugin system)
- Basic `$SYS` topics
- TCP and websocket support
- SSL support over TCP and websocket
- Plugin system

## Project Status and Roadmap

The current focus is to build setup the project infrastructure for the new fork.
From there the goal is to fix outstanding known issues and clean up the code.

| Version | hbmqtt compatibility | Supported Python Versions | PyPi Release |
|---------|---------------------|-------------------------|--------------|
| 0.10.x | YES - Drop-in Replacement | 3.7* | 0.10.1 |
| 0.11.x | NO - Module renamed and small API differences | 3.7 - 3.10 | No release yet |

\* Due to a change in Python 3.8 where the semantics of asyncio.CancelledError was changed to be a subclass of BaseException instead of Exception, old versions of hbmqtt and aMQTT will break, see https://github.com/Yakifo/amqtt/issues/133. Therefore only 3.7 is mentioned as supported version for 0.10.x.

## Getting started

`amqtt` is available on [PyPI](https://pypi.python.org/pypi/amqtt) and can be installed simply using `pip`:

```bash
$ pip install amqtt
```

Documentation is available on [Read the Docs](http://amqtt.readthedocs.org/).

Bug reports, patches and suggestions welcome! Just [open an issue](https://github.com/Yakifo/amqtt/issues/new) or join the [gitter community](https://gitter.im/amqtt/community).
