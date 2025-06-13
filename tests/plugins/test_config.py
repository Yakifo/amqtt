import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import pytest
import yaml

from amqtt.broker import Broker
from yaml import CLoader as Loader
from dacite import from_dict, Config, UnexpectedDataError

from amqtt.client import MQTTClient
from amqtt.errors import PluginLoadError

logger = logging.getLogger(__name__)

plugin_config = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestSimplePlugin:
   - tests.plugins.mocks.TestConfigPlugin:
       option1: 1
       option2: bar
"""


plugin_invalid_config_one = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestSimplePlugin:
       option1: 1
       option2: bar
"""

plugin_invalid_config_two = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestConfigPlugin:
"""

plugin_config_auth = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestAuthPlugin:
"""

plugin_config_topic = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestTopicPlugin:
"""

# @pytest.mark.asyncio
# async def test_plugin_config_extra_fields():
#
#     cfg: dict[str, Any] = yaml.load(plugin_invalid_config_one, Loader=Loader)
#
#     with pytest.raises(PluginLoadError):
#         _ = Broker(config=cfg)
#
#
# @pytest.mark.asyncio
# async def test_plugin_config_missing_fields():
#     cfg: dict[str, Any] = yaml.load(plugin_invalid_config_one, Loader=Loader)
#
#     with pytest.raises(PluginLoadError):
#         _ = Broker(config=cfg)
#
#
# @pytest.mark.asyncio
# async def test_alternate_plugin_load():
#
#     cfg: dict[str, Any] = yaml.load(plugin_config, Loader=Loader)
#
#     broker = Broker(config=cfg)
#     await broker.start()
#     await broker.shutdown()
#
#
# @pytest.mark.asyncio
# async def test_auth_plugin_load():
#     cfg: dict[str, Any] = yaml.load(plugin_config_auth, Loader=Loader)
#     broker = Broker(config=cfg)
#     await broker.start()
#     await asyncio.sleep(0.5)
#
#     client1 = MQTTClient()
#     await client1.connect()
#     await client1.publish('my/topic', b'my message')
#     await client1.disconnect()
#
#     await asyncio.sleep(0.5)
#     await broker.shutdown()
#
#
# @pytest.mark.asyncio
# async def test_topic_plugin_load():
#     cfg: dict[str, Any] = yaml.load(plugin_config_topic, Loader=Loader)
#     broker = Broker(config=cfg)
#     await broker.start()
#     await broker.shutdown()
