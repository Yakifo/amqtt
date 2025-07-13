import logging
from typing import Any

try:
    from enum import Enum, StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass

from dacite import from_dict, Config

from amqtt.contexts import BrokerConfig, ListenerType

logger = logging.getLogger(__name__)


def test_entrypoint_broker_config(caplog):
    test_cfg: dict[str, Any] = {
        "listeners": {
            "default": {"type": "tcp", "bind": "127.0.0.1:1883", "max_connections": 10},
        },
        'sys_interval': 1,
        'auth': {
            'allow_anonymous': True
        }
    }
    if 'plugins' not in test_cfg:
        test_cfg['plugins'] = None
    # cfg: dict[str, Any] = yaml.load(config, Loader=Loader)


    broker_config = from_dict(data_class=BrokerConfig, data=test_cfg, config=Config(cast=[StrEnum, ListenerType]))
    assert isinstance(broker_config, BrokerConfig)

    assert broker_config.plugins is None


