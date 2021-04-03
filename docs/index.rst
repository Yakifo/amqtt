aMQTT
======

``aMQTT`` is an open source `MQTT`_ client and broker implementation.

Built on top of :mod:`asyncio`, Python's standard asynchronous I/O framework, aMQTT provides a straightforward API
based on coroutines, making it easy to write highly concurrent applications.

Features
--------

aMQTT implements the full set of `MQTT 3.1.1`_ protocol specifications and provides the following features:

- Support QoS 0, QoS 1 and QoS 2 messages flow
- Client auto-reconnection on network lost
- Authentication through password file (more methods can be added through a plugin system)
- Basic ``$SYS`` topics
- TCP and websocket support
- SSL support over TCP and websocket
- Plugin system


Requirements
------------

aMQTT is built on Python's `asyncio`.
It requires Python 3.6 or newer.

Installation
------------

It is not recommended to install third-party library in Python system packages directory. The preferred way for
installing aMQTT is to create a virtual environment and then install all the dependencies you need. Refer to
`PEP 405`_ to learn more.

Once you have a environment setup and ready, aMQTT can be installed with the following command ::

  (venv) $ pip install amqtt

``pip`` will download and install aMQTT and all its dependencies.


User guide
----------

If you need aMQTT for running a MQTT client or deploying a MQTT broker, the :doc:`quickstart` describes how to use console scripts provided by aMQTT.

If you want to develop an application which needs to connect to a MQTT broker, the :doc:`references/mqttclient` documentation explains how to use aMQTT API for connecting, publishing and subscribing with a MQTT broker.

If you want to run you own MQTT broker, th :doc:`references/broker` reference documentation explains how to embed a MQTT broker inside a Python application.

News and updates are listed in the :doc:`changelog`.


.. _MQTT: http://www.mqtt.org
.. _MQTT 3.1.1: http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
.. _PEP 405: https://www.python.org/dev/peps/pep-0405/

.. toctree::
   :maxdepth: 2
   :hidden:

   quickstart
   changelog
   transition
   references/index
   license

