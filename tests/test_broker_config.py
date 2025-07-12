import logging
import pytest
from dataclasses import dataclass, field
from pathlib import Path

from dacite import from_dict, Config, UnexpectedDataError
from enum import StrEnum

from amqtt.contexts import BrokerConfig, ListenerConfig, Dictable

logger = logging.getLogger(__name__)


def _test_broker_config():
    # Parse with dacite
    config = from_dict(data_class=BrokerConfig, data=data, config=Config(cast=[StrEnum]))

    assert isinstance(config, BrokerConfig)
    assert isinstance(config.listeners['default'], ListenerConfig)
    assert isinstance(config.listeners['secure'], ListenerConfig)

    default = config.listeners['default']
    secure = config.listeners['secure']
    secure_one = secure.copy()
    secure_two = secure.copy()

    secure_one |= default

    assert secure_one.max_connections == 50
    assert secure_one.bind == '0.0.0.0:8883'
    assert secure_one.cafile == Path('ca.key')

    secure_two.update(default)
    assert secure_two.max_connections == 50
    assert secure_two.bind == '0.0.0.0:8883'
    assert secure_two.cafile == Path('ca.key')



