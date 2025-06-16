# Changelog

## 0.11.0

- upgrades to support python 3.10, 3.11, 3.12 and 3.13
- complete type hinting of the entire codebase
- linting with ruff, pylint and mypy to keep the codebase consistent in format and structure
- github workflow CI of linting before pull requests can be merged
- run linting with git pre-commit hooks 
- add docker container
- switch to discord
- updates to community contribution guidance, code of conduct, etc. 
- overhaul of the documentation, including move to mkdocs with the materials UI
- updated plugin documentation and full docs for the broker/client configuration 
- updated doc strings and cli help messages, including auto generation of those aspects into the docs
- [Issue #215](https://github.com/Yakifo/amqtt/issues/215) test_sys.py fails on github, but not locally
- [Issue #210](https://github.com/Yakifo/amqtt/issues/210) NoDataError thrown instead of ConnectError when client fails authentication
- [Issue #199](https://github.com/Yakifo/amqtt/issues/199) will message being sent even if client properly disconnects
- [Issue #180](https://github.com/Yakifo/amqtt/issues/180) plugin broker sys: incorrect uptime topic
- [Issue #178](https://github.com/Yakifo/amqtt/issues/178) consolidate broker configuration documentation
- [Issue #170](https://github.com/Yakifo/amqtt/issues/170) compatibility test cases: paho-mqtt
- [Issue #159](https://github.com/Yakifo/amqtt/issues/159) Client last will (LWT) example and documentation
- [Issue #157](https://github.com/Yakifo/amqtt/issues/157) loop = asyncio.get_event_loop() is deprecated
- [Issue #154](https://github.com/Yakifo/amqtt/issues/154) broker rejects connect with empty will message
- [Issue #144](https://github.com/Yakifo/amqtt/issues/144) Allow amqtt.client.MQTTClient to always reconnect via config
- [Issue #105](https://github.com/Yakifo/amqtt/issues/105) Add stack traces to logging
- [Issue #95](https://github.com/Yakifo/amqtt/issues/95) asyncio.get_event_loop() deprecated in Python 3.10
- [Issue #94](https://github.com/Yakifo/amqtt/issues/94) test matrix for dependencies
- [Issue #70](https://github.com/Yakifo/amqtt/issues/70) event and plugin documentation
- [Issue #67](https://github.com/Yakifo/amqtt/issues/67) MQTTClient fails to raise appropriate exception if URI is broken
- [Issue #51](https://github.com/Yakifo/amqtt/issues/51) failing plugin kills the broker
- [Issue #48](https://github.com/Yakifo/amqtt/issues/48) Setup unit tests running against different versions of dependencies
- [Issue #35](https://github.com/Yakifo/amqtt/issues/35) plugin interface and optimization


## 0.10.0

- First release under new package name: amqtt
- Reworked unit tests
- Dropped support for python3.5 and earlier
- Added support for python3.8 and 3.9
- Pass in loop to PluginManager, from [PR #126](https://github.com/beerfactory/hbmqtt/pull/126)
- Fixes taboo topic checking without session username, from [PR #151](https://github.com/beerfactory/hbmqtt/pull/151)
- Move scripts module into hbmqtt module, from [PR #167](https://github.com/beerfactory/hbmqtt/pull/167)
- Download mosquitto certificate on the fly
- Importing `hbmqtt` is deprecated, use `amqtt`
- Security fix: If an attacker could produce a KeyError inside an authentication plugin, the authentication was accepted instead of rejected

## 0.9.5

- fixes: [milestone 0.9.5](https://github.com/njouanin/hbmqtt/milestone/11?closed=1)
- fixes: [milestone 0.9.3](https://github.com/njouanin/hbmqtt/milestone/10?closed=1)

## 0.9.2

- fixes: [milestone 0.9.2](https://github.com/beerfactory/hbmqtt/milestone/9?closed=1)

## 0.9.1

- See commit log

## 0.9.0

- fixes: [milestone 0.9.0](https://github.com/beerfactory/hbmqtt/milestone/8?closed=1)
- improve plugin performance
- support Python 3.6
- upgrade to `websockets` 3.3.0

## 0.8.0

- fixes: [milestone 0.8.0](https://github.com/njouanin/hbmqtt/milestone/7?closed=1)

## 0.7.3

- fix deliver message client method to raise TimeoutError ([#40](https://github.com/beerfactory/hbmqtt/issues/40))
- fix topic filter matching in broker ([#41](https://github.com/beerfactory/hbmqtt/issues/41))

Version 0.7.2 has been jumped due to troubles with pypi...

## 0.7.1

- Fix [duplicated $SYS topic name](https://github.com/beerfactory/hbmqtt/issues/37)

## 0.7.0

- Fix a [series of issues](https://github.com/beerfactory/hbmqtt/issues?q=milestone%3A0.7+is%3Aclosed) reported by [Christoph Krey](https://github.com/ckrey)

## 0.6.3

- Fix issue [#22](https://github.com/beerfactory/hbmqtt/issues/22)

## 0.6.2

- Fix issue [#20](https://github.com/beerfactory/hbmqtt/issues/20) (`mqtt` subprotocol was missing)
- Upgrade to `websockets` 3.0

## 0.6.1

- Fix issue [#19](https://github.com/beerfactory/hbmqtt/issues/19)

## 0.6

- Added compatibility with Python 3.5
- Rewritten documentation
- Add command-line tools `amqtt`, `amqtt_pub` and `amqtt_sub`
