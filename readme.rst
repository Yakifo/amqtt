|license| |ci| |coverage| |rtfm| |gitter| |python_versions| |python_wheel| |PyPI|

.. |license| image:: https://img.shields.io/github/license/Yakifo/amqtt?style=flat-square
    :target: https://amqtt.readthedocs.io/en/latest/
    :alt: MIT licensed

.. |ci| image:: https://img.shields.io/github/workflow/status/Yakifo/amqtt/Python%20package?style=flat-square
    :target: https://github.com/Yakifo/amqtt/actions/workflows/python-package.yml

.. |coverage| image:: https://img.shields.io/coveralls/github/Yakifo/amqtt?style=flat-square
    :target: https://coveralls.io/github/Yakifo/amqtt?branch=master

.. |rtfm| image:: https://img.shields.io/readthedocs/amqtt?style=flat-square
    :target: https://amqtt.readthedocs.io/en/latest/
    :alt: Documentation Status

.. |gitter| image:: https://img.shields.io/gitter/room/Yakifo/amqtt?style=flat-square
    :target: https://gitter.im/amqtt/community
    :alt: 'Join the chat at https://gitter.im/amqtt/community'

.. |python_versions| image:: https://img.shields.io/pypi/pyversions/amqtt?style=flat-square
    :alt: Python Version

.. |python_wheel| image:: https://img.shields.io/pypi/wheel/amqtt?style=flat-square 
    :alt: supports python wheel

.. |PyPI| image:: https://img.shields.io/pypi/v/amqtt?style=flat-square
    :target: https://pypi.org/project/amqtt/
    :alt: PyPI


aMQTT
======

``aMQTT`` is an open source `MQTT`_ client and broker implementation.

Built on top of `asyncio`_, Python's standard asynchronous I/O framework, aMQTT provides a straightforward API
based on coroutines, making it easy to write highly concurrent applications.

It was forked from `HBMQTT`_ after it was deprecated by the original author.


.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _HBMQTT: https://github.com/beerfactory/hbmqtt

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


Project Status and Roadmap
---------------------------

The current focus is to build setup the project infrastructure for the new fork.
From there the goal is to fix outstanding known issues and clean up the code.

+----------+---------------------------+----------------------------+--------------+
| Version  | hbmqtt compatibility      | Supported Python Versions  | PyPi Release |
+----------+---------------------------+----------------------------+--------------+
| 0.10.x   | YES - Drop-in Replacement | 3.7 - 3.9                  | 0.10.1       |
+----------+---------------------------+----------------------------+--------------+
| 0.11.x   | NO - Module renamed       | 3.7 - 3.10                 | No release   |
|          | and small API differences |                            | yet          |
+----------+---------------------------+----------------------------+--------------+


Getting started
---------------

`amqtt` is available on `Pypi <https://pypi.python.org/pypi/amqtt>`_ and can installed simply using ``pip`` :
::

    $ pip install amqtt

Documentation is available on `Read the Docs`_.

Bug reports, patches and suggestions welcome! Just `open an issue`_ or join the `gitter channel`_.



.. _MQTT: http://www.mqtt.org
.. _MQTT 3.1.1: http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
.. _Read the Docs: http://amqtt.readthedocs.org/
.. _open an issue: https://github.com/Yakifo/amqtt/issues/new
.. _gitter channel: https://gitter.im/amqtt/community
