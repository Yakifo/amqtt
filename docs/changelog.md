# Changelog

## 0.11.3

* Structural elements for the 0.11.3 release https://github.com/Yakifo/amqtt/pull/265
* Release Candidate Branch for 0.11.3 https://github.com/Yakifo/amqtt/pull/272
* update the configuration for the broker running at test.amqtt.io  https://github.com/Yakifo/amqtt/pull/271
* Improved broker script logging https://github.com/Yakifo/amqtt/pull/277
* test.amqtt.io dashboard cleanup  https://github.com/Yakifo/amqtt/pull/278
* Structured broker and client configurations https://github.com/Yakifo/amqtt/pull/269
* Determine auth & topic access via external http server https://github.com/Yakifo/amqtt/pull/262
* Plugin: authentication against a relational database  https://github.com/Yakifo/amqtt/pull/280
* Fixes #247 : expire disconnected sessions https://github.com/Yakifo/amqtt/pull/279
* Expanded structure for plugin documentation https://github.com/Yakifo/amqtt/pull/281
* Yakifo/amqtt#120 confirms : validate example is functioning https://github.com/Yakifo/amqtt/pull/284
* Yakifo/amqtt#39 : adding W0718 'broad exception caught' https://github.com/Yakifo/amqtt/pull/285
* Documentation improvement for 0.11.3 https://github.com/Yakifo/amqtt/pull/286
* Plugin naming convention https://github.com/Yakifo/amqtt/pull/288
* embed amqtt into an existing server https://github.com/Yakifo/amqtt/pull/283
* Plugin: rebuild of session persistence https://github.com/Yakifo/amqtt/pull/256
* Plugin: determine authentication based on X509 certificates https://github.com/Yakifo/amqtt/pull/264
* Plugin: device 'shadows' to bridge device online/offline states https://github.com/Yakifo/amqtt/pull/282
* Plugin: authenticate against LDAP server https://github.com/Yakifo/amqtt/pull/287
* Sample: broker and client communicating with mqtt over unix socket https://github.com/Yakifo/amqtt/pull/291
* Plugin: jwt authentication and authorization https://github.com/Yakifo/amqtt/pull/289

## 0.11.2

-  config-file based plugin loading   [PR #240](https://github.com/Yakifo/amqtt/pull/240)
-  dockerfile build update to support psutils   [PR #239](https://github.com/Yakifo/amqtt/pull/239)
-  pass client session info to event callbacks   [PR #241](https://github.com/Yakifo/amqtt/pull/241)
-  Require at least one auth   [PR #244](https://github.com/Yakifo/amqtt/pull/244)
-  improvements in retaining messages   [PR #248](https://github.com/Yakifo/amqtt/pull/248)
-  updating docker compose with resource limits   [PR #253](https://github.com/Yakifo/amqtt/pull/253)
-  improve static type checking for plugin's `Config` class   [PR #249](https://github.com/Yakifo/amqtt/pull/249)
-  broker shouldn't allow clients to publish to '$' topics   [PR #254](https://github.com/Yakifo/amqtt/pull/254)
-  publishing to a topic with `*` is allowed, while `#` and `+` are not   [PR #251](https://github.com/Yakifo/amqtt/pull/251)
-  updated samples; plugin config consistency (yaml and python dict)   [PR #252](https://github.com/Yakifo/amqtt/pull/252)
-  add cpu, mem and broker version to dashboard   [PR #257](https://github.com/Yakifo/amqtt/pull/257)
- [Issue 246](https://github.com/Yakifo/amqtt/issues/246) don't retain QoS 1 or 2 messages if client connects with clean session true
- [Issue 175](https://github.com/Yakifo/amqtt/issues/175) plugin examples
- [Issue 81](https://github.com/Yakifo/amqtt/issues/81) Abstract factory for plugins
- [Issue 74](https://github.com/Yakifo/amqtt/issues/74) 模拟500个客户端并发，连接broker。
- [Issue 60](https://github.com/Yakifo/amqtt/issues/60) amqtt server not relaying traffic
- [Issue 31](https://github.com/Yakifo/amqtt/issues/31) Plugin config in yaml file not under - plugins entry
- [Issue 27](https://github.com/Yakifo/amqtt/issues/27) don't retain messages from anonymous clients
- [Issue 250](https://github.com/Yakifo/amqtt/issues/250) client doesn't prevent publishing to wildcard topics
- [Issue 245](https://github.com/Yakifo/amqtt/issues/245) prevent clients from publishing to `$` topics
- [Issue 196](https://github.com/Yakifo/amqtt/issues/196) proposal: enhancement to broker plugin configuration
- [Issue 187](https://github.com/Yakifo/amqtt/issues/187) anonymous login allowed even if plugin isn't enabled
- [Issue 123](https://github.com/Yakifo/amqtt/issues/123) Messages sent to mqtt can be consumed in time, but they occupy more and more memory

## 0.11.1

- [PR #226](https://github.com/Yakifo/amqtt/pull/226) Consolidate super classes for plugins
- [PR #227](https://github.com/Yakifo/amqtt/pull/227) Update sample files
- [PR #229](https://github.com/Yakifo/amqtt/pull/229) & [PR #228](https://github.com/Yakifo/amqtt/pull/228) Broken pypi and test.amqtt.io links
- [PR #232](https://github.com/Yakifo/amqtt/pull/234) $SYS additions for cpu & mem.

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


## 0.10.2

- create the necessary .readthedocs.yaml to generate sphinx docs from the 0.10.x series

## 0.10.1

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
