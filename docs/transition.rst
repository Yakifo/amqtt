Transitioning from HBMQTT to aMQTT
==================================

This document is for those porting from HBMQTT to aMQTT.
Basically you can search and replace ``hbmqtt`` with ``amqtt`` and all should work out.
Details below.


Imports
-------

The module changed from ``hbmqtt`` to ``amqtt``.
For the 0.10.x releases it will still be possible to ``import hbmqtt``.
In 0.11.x only ``amqtt`` will work.

Since the ``amqtt`` package does provide a ``hbmqtt`` module, installing the ``hbmqtt`` package in the same python installation is not possible.


Random Client ID
----------------

When not providing a client_id, a random id is automatically generated.
These names were also changed from ``hbmqtt/<random>`` to ``amqtt/<random>``.

plugins / entrypoints
---------------------

If you make use of python's entrypoint system to build aMQTT plugins, make sure to use the ``amqtt.*.plugins`` names instead of ``hbmqtt.*.plugins`` names.
During the transition plugins with ``hbmqtt`` entrypoint should keep working for 0.10.x releases.


CLI tools
---------

Will also be renamed.