Changelog
---------

0.11.0 unreleased
-----------------
 * removed hbmqtt compatibility, importing amqtt is now mandatory
 * removed loop parameter from all functions
 * Python 3.10 compatibility
 * Fixed a major bug in plugin api, see https://github.com/Yakifo/amqtt/pull/92

0.10.0 - 2021-08-04
-------------------

 * first release under new package name: amqtt
 * reworked unit tests
 * dropped support for python3.5 and earlier
 * added support for python3.8 and 3.9
 * Pass in loop to PluginManager, from https://github.com/beerfactory/hbmqtt/pull/126
 * Fixes taboo topic checking without session username, from https://github.com/beerfactory/hbmqtt/pull/151
 * Move scripts module into hbmqtt module, from https://github.com/beerfactory/hbmqtt/pull/167
 * Download mosquitto certificate on the fly
 * importing `hbmqtt` is deprecated, use `amqtt`
 * Security fix: If an attacker could produce a KeyError inside an authentication plugin, the authentication was accepted instead of rejected

0.9.5
.....

* fix `more issues <https://github.com/beerfactory/hbmqtt/milestone/11?closed=1>`_
* fix a `few issues <https://github.com/beerfactory/hbmqtt/milestone/10?closed=1>`_

0.9.2
.....

* fix a `few issues <https://github.com/beerfactory/hbmqtt/milestone/9?closed=1>`_


0.9.1
.....

* See commit log


0.9.0
.....

* fix a `serie of issues <https://github.com/beerfactory/hbmqtt/milestone/8?closed=1>`_
* improve plugin performance
* support Python 3.6
* upgrade to ``websockets`` 3.3.0

0.8.0
.....

* fix a `serie of issues <https://github.com/beerfactory/hbmqtt/milestone/7?closed=1>`_

0.7.3
.....

* fix deliver message client method to raise TimeoutError (`#40 <https://github.com/beerfactory/hbmqtt/issues/40>`_)
* fix topic filter matching in broker (`#41 <https://github.com/beerfactory/hbmqtt/issues/41>`_)

Version 0.7.2 has been jumped due to troubles with pypi...

0.7.1
.....

* Fix `duplicated $SYS topic name <https://github.com/beerfactory/hbmqtt/issues/37>`_ .

0.7.0
.....

* Fix a `serie of issues <https://github.com/beerfactory/hbmqtt/issues?q=milestone%3A0.7+is%3Aclosed>`_ reported by `Christoph Krey <https://github.com/ckrey>`_

0.6.3
.....

* Fix issue `#22 <https://github.com/beerfactory/hbmqtt/issues/22>`_.

0.6.2
.....

* Fix issue `#20 <https://github.com/beerfactory/hbmqtt/issues/20>`_  (``mqtt`` subprotocol was missing).
* Upgrade to ``websockets`` 3.0.

0.6.1
.....

* Fix issue `#19 <https://github.com/beerfactory/hbmqtt/issues/19>`_

0.6
...

* Added compatibility with Python 3.5.
* Rewritten documentation.
* Add command-line tools :doc:`references/hbmqtt`, :doc:`references/hbmqtt_pub` and :doc:`references/hbmqtt_sub`.