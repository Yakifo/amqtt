import logging
import pytest
from dataclasses import dataclass, field
from pathlib import Path

from dacite import from_dict, Config, UnexpectedDataError
from enum import StrEnum

from amqtt.contexts import BrokerConfig, ListenerConfig, Dictable

logger = logging.getLogger(__name__)

@dataclass
class NestedData(Dictable):
    nested_one: int | None = None
    nested_two: str | None = None
    nested_three: str | None = "empty option"


@dataclass
class MainData(Dictable):
    main_one: str | None = None
    main_two: str | None = 2
    main_three: dict[str, NestedData] | None = field(default_factory=dict)


data_a = {
    'main_one': 'value main one',
    'main_three': {
        'nested_key_one': {
            'nested_one': 101,
            'nested_two': 'value nested two'
        }
    }
}

data_b = {
    'option_one': 'value ten'
}

data_c = {
    'main_two': 'value main two',
    'main_three': {
        'nested_key_one': {
            'nested_two': 'other nested two'
        },
        'nested_key_two': {
            'nested_one': 202,
            'nested_three': 'other nested three'
        }
    }
}


def test_mismatched_data():

    with pytest.raises(UnexpectedDataError):
        _ = from_dict(data_class=MainData, data=data_b, config=Config(cast=[StrEnum], strict=True))

def test_nested_data():
    main_a = from_dict(data_class=MainData, data=data_a, config=Config(cast=[StrEnum], strict=True))
    main_c = from_dict(data_class=MainData, data=data_c, config=Config(cast=[StrEnum], strict=True))

    main_a.update(main_c)

    assert isinstance(main_c, MainData)
    assert isinstance(main_c, MainData)
    assert isinstance(main_c.main_three, dict)
    assert 'nested_key_one' in main_c.main_three
    assert isinstance(main_c.main_three['nested_key_one'], NestedData)
    assert 'nested_key_two' in main_c.main_three

    assert main_c.main_three['nested_key_two'].nested_two == 'value nested two'

    assert main_a.main_one == 'value main one'
    assert main_a.main_two == 'value main two'
    assert main_a.main_three['nested_key_one'].nested_two == 'other nested two'
    assert main_a.main_three['nested_key_one'] == 'value twelve'
    assert main_a.main_three['nested_key_one'] == 'value three'


data = {
    "listeners": {
        "default": {
            "bind": "0.0.0.0:1883",
            "max_connections": 50
        },
        "secure": {
            "bind": "0.0.0.0:8883",
            "cafile": "ca.key"
        }
    }
}


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



