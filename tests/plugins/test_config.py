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
from amqtt.errors import PluginLoadError, ConnectError, PluginCoroError
from amqtt.mqtt.constants import QOS_0

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

plugin_coro_error_config = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestCoroErrorPlugin:
"""

plugin_config_auth = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestAuthPlugin:
"""

plugin_config_no_auth = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestNoAuthPlugin:
"""


plugin_config_topic = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - amqtt.plugins.authentication.AnonymousAuthPlugin
   - tests.plugins.mocks.TestAllowTopicPlugin:
"""


plugin_config_topic_block = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - amqtt.plugins.authentication.AnonymousAuthPlugin
   - tests.plugins.mocks.TestBlockTopicPlugin:
"""



@pytest.mark.asyncio
async def test_plugin_config_extra_fields():

    cfg: dict[str, Any] = yaml.load(plugin_invalid_config_one, Loader=Loader)

    with pytest.raises(PluginLoadError):
        _ = Broker(config=cfg)


@pytest.mark.asyncio
async def test_plugin_config_missing_fields():
    cfg: dict[str, Any] = yaml.load(plugin_invalid_config_one, Loader=Loader)

    with pytest.raises(PluginLoadError):
        _ = Broker(config=cfg)


@pytest.mark.asyncio
async def test_alternate_plugin_load():

    cfg: dict[str, Any] = yaml.load(plugin_config, Loader=Loader)

    broker = Broker(config=cfg)
    await broker.start()
    await broker.shutdown()


@pytest.mark.asyncio
async def test_coro_error_plugin_load():

    cfg: dict[str, Any] = yaml.load(plugin_coro_error_config, Loader=Loader)

    with pytest.raises(PluginCoroError):
        _ = Broker(config=cfg)


@pytest.mark.asyncio
async def test_auth_plugin_load():
    cfg: dict[str, Any] = yaml.load(plugin_config_auth, Loader=Loader)
    broker = Broker(config=cfg)
    await broker.start()
    await asyncio.sleep(0.5)

    client1 = MQTTClient()
    await client1.connect()
    await client1.publish('my/topic', b'my message')
    await client1.disconnect()

    await asyncio.sleep(0.5)
    await broker.shutdown()


@pytest.mark.asyncio
async def test_no_auth_plugin_load():
    cfg: dict[str, Any] = yaml.load(plugin_config_no_auth, Loader=Loader)
    broker = Broker(config=cfg)
    await broker.start()
    await asyncio.sleep(0.5)

    client1 = MQTTClient(config={'auto_reconnect': False})
    with pytest.raises(ConnectError):
        await client1.connect()

    await asyncio.sleep(0.5)
    await broker.shutdown()


@pytest.mark.asyncio
async def test_allow_topic_plugin_load():
    cfg: dict[str, Any] = yaml.load(plugin_config_topic, Loader=Loader)
    broker = Broker(config=cfg)
    await broker.start()
    await asyncio.sleep(0.5)

    client2 = MQTTClient(config={'auto_reconnect': False})
    await client2.connect()
    await client2.subscribe([
        ('my/topic', QOS_0)
    ])

    client1 = MQTTClient(config={'auto_reconnect': True})
    await client1.connect()
    await client1.publish('my/topic', b'my message')

    message = await client2.deliver_message(timeout_duration=1)
    assert message.topic == 'my/topic'
    assert message.data == b'my message'

    await client2.disconnect()
    await client1.disconnect()

    await broker.shutdown()


@pytest.mark.asyncio
async def test_block_topic_plugin_load():
    cfg: dict[str, Any] = yaml.load(plugin_config_topic_block, Loader=Loader)
    broker = Broker(config=cfg)
    await broker.start()
    await asyncio.sleep(0.5)

    client2 = MQTTClient(config={'auto_reconnect': False})
    await client2.connect()
    await client2.subscribe([
        ('my/topic', QOS_0)
    ])

    client1 = MQTTClient(config={'auto_reconnect': True})
    await client1.connect()
    await client1.publish('my/topic', b'my message')

    with pytest.raises(asyncio.TimeoutError):
        message = await client2.deliver_message(timeout_duration=1)
        logger.debug(f"msg received: {message.topic} >> {message.data}")

    await client2.disconnect()
    await client1.disconnect()

    await broker.shutdown()

plugin_yaml_list_config_one = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestSimplePlugin:
   - tests.plugins.mocks.TestConfigPlugin:
       option1: 1
       option2: bar
       option3: 3
"""

plugin_yaml_list_config_two = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   - tests.plugins.mocks.TestSimplePlugin:
   - tests.plugins.mocks.TestConfigPlugin:
       option1: 1
       option2: bar
       option3: 3
"""

plugin_yaml_dict_config = """---
listeners:
  default:
    type: tcp
    bind: 0.0.0.0:1883
plugins:
   tests.plugins.mocks.TestSimplePlugin:
   tests.plugins.mocks.TestConfigPlugin:
    option1: 1
    option2: bar
    option3: 3
"""

plugin_empty_dict_config = {
    'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1'}},
    'plugins': {
        'tests.plugins.mocks.TestSimplePlugin': {},
    }
}

plugin_dict_option_config = {
    'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1'}},
    'plugins': {
        'tests.plugins.mocks.TestConfigPlugin': {'option1': 1, 'option2': 'bar', 'option3': 3}
    }
}

@pytest.mark.asyncio
async def test_plugin_yaml_list_config():
    cfg: dict[str, Any] = yaml.load(plugin_yaml_list_config_one, Loader=Loader)
    broker = Broker(config=cfg)

    await asyncio.sleep(0.5)
    plugin = broker.plugins_manager.get_plugin('TestConfigPlugin')
    assert getattr(plugin.context.config, 'option1', None) == 1
    assert getattr(plugin.context.config, 'option3', None) == 3

    cfg: dict[str, Any] = yaml.load(plugin_yaml_list_config_two, Loader=Loader)
    broker = Broker(config=cfg)

    await asyncio.sleep(0.5)
    plugin = broker.plugins_manager.get_plugin('TestConfigPlugin')
    assert getattr(plugin.context.config, 'option1', None) == 1
    assert getattr(plugin.context.config, 'option3', None) == 3


@pytest.mark.asyncio
async def test_plugin_yaml_dict_config():
    cfg: dict[str, Any] = yaml.load(plugin_yaml_dict_config, Loader=Loader)
    broker = Broker(config=cfg)

    await asyncio.sleep(0.5)
    assert broker.plugins_manager.get_plugin('TestSimplePlugin') is not None


@pytest.mark.asyncio
async def test_plugin_empty_dict_config():
    broker = Broker(config=plugin_empty_dict_config)

    await asyncio.sleep(0.5)
    assert broker.plugins_manager.get_plugin('TestSimplePlugin') is not None


@pytest.mark.asyncio
async def test_plugin_option_dict_config():
    broker = Broker(config=plugin_dict_option_config)

    await asyncio.sleep(0.5)
    plugin = broker.plugins_manager.get_plugin('TestConfigPlugin')
    assert getattr(plugin.context.config, 'option1', None) == 1
    assert getattr(plugin.context.config, 'option3', None) == 3
