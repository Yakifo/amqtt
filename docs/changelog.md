# Changelog

## 0.11.0

- Removed hbmqtt compatibility, importing amqtt is now mandatory
- Removed loop parameter from all functions
- Python 3.10 to 3.13 compatibility
- Fixed a major bug in plugin api, see [PR #92](https://github.com/Yakifo/amqtt/pull/92)
- Migrated from `docopts` to `typer`

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
