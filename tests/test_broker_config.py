import logging
from pathlib import Path
from typing import Any

import pytest

try:
    from enum import Enum, StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass

from dacite import from_dict, Config

from amqtt.contexts import BrokerConfig, ClientConfig, ConnectionConfig, ListenerConfig, ListenerType, TopicConfig, WillConfig

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


def test_broker_config_from_dict_none_uses_defaults() -> None:
    broker_config = BrokerConfig.from_dict(None)

    assert "default" in broker_config.listeners
    assert broker_config.plugins is not None


def test_broker_config_from_dict_normalizes_topic_check_and_plugin_lists() -> None:
    broker_config = BrokerConfig.from_dict(
        {
            "listeners": {"default": {"bind": "127.0.0.1:1883"}},
            "topic-check": {"enabled": True},
            "plugins": [
                "amqtt.plugins.authentication.AnonymousAuthPlugin",
                {"amqtt.plugins.topic_checking.TopicTabooPlugin": {"topic": "prohibited"}},
            ],
        },
    )

    assert broker_config.topic_check == {"enabled": True}
    assert broker_config.plugins == {
        "amqtt.plugins.authentication.AnonymousAuthPlugin": {},
        "amqtt.plugins.topic_checking.TopicTabooPlugin": {"topic": "prohibited"},
    }


def test_listener_config_requires_certfile_and_keyfile_together(tmp_path: Path) -> None:
    certfile = tmp_path / "cert.pem"
    certfile.write_text("cert", encoding="utf-8")

    with pytest.raises(ValueError, match="both are required"):
        ListenerConfig(certfile=certfile)
    with pytest.raises(ValueError, match="both are required"):
        ListenerConfig(keyfile=certfile)


def test_listener_config_converts_existing_file_fields_to_paths(tmp_path: Path) -> None:
    cafile = tmp_path / "ca.pem"
    certfile = tmp_path / "cert.pem"
    keyfile = tmp_path / "key.pem"
    capath = tmp_path / "capath"
    capath.mkdir()
    for path in (cafile, certfile, keyfile):
        path.write_text("placeholder", encoding="utf-8")

    listener_config = ListenerConfig(
        cafile=str(cafile),
        capath=str(capath),
        certfile=str(certfile),
        keyfile=str(keyfile),
    )

    assert listener_config.cafile == cafile
    assert listener_config.capath == capath
    assert listener_config.certfile == certfile
    assert listener_config.keyfile == keyfile


def test_listener_config_rejects_missing_file_fields(tmp_path: Path) -> None:
    keyfile = tmp_path / "key.pem"
    keyfile.write_text("key", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="certfile"):
        ListenerConfig(certfile=tmp_path / "missing-cert.pem", keyfile=keyfile)


def test_connection_config_requires_certfile_and_keyfile_together() -> None:
    with pytest.raises(ValueError, match="both are required"):
        ConnectionConfig(certfile="client.pem")
    with pytest.raises(ValueError, match="both are required"):
        ConnectionConfig(keyfile="client-key.pem")


def test_connection_config_converts_file_fields_to_paths() -> None:
    connection_config = ConnectionConfig(
        cafile="ca.pem",
        capath="certs",
        certfile="client.pem",
        keyfile="client-key.pem",
    )

    assert connection_config.cafile == Path("ca.pem")
    assert connection_config.capath == Path("certs")
    assert connection_config.certfile == Path("client.pem")
    assert connection_config.keyfile == Path("client-key.pem")


@pytest.mark.parametrize("qos", [-1, 3])
def test_topic_config_rejects_invalid_qos(qos: int) -> None:
    with pytest.raises(ValueError, match="Topic config"):
        TopicConfig(qos=qos)


@pytest.mark.parametrize("qos", [-1, 3])
def test_will_config_rejects_invalid_qos(qos: int) -> None:
    with pytest.raises(ValueError, match="Will config"):
        WillConfig(topic="will/topic", message="payload", qos=qos)


def test_client_config_from_dict_none_uses_defaults() -> None:
    client_config = ClientConfig.from_dict(None)

    assert client_config.connection.uri == "mqtt://127.0.0.1:1883"
    assert client_config.default_qos == 0


def test_client_config_rejects_invalid_default_qos() -> None:
    with pytest.raises(ValueError, match="Client config"):
        ClientConfig(default_qos=3)


def test_client_config_uses_deprecated_broker_config() -> None:
    broker_connection = ConnectionConfig(uri="mqtt://broker.example:1883")

    with pytest.warns(UserWarning, match="broker"):
        client_config = ClientConfig(broker=broker_connection)

    assert client_config.connection is broker_connection


def test_client_config_rejects_mismatched_connection_cert_and_key() -> None:
    connection = ConnectionConfig(certfile="client.pem", keyfile="client-key.pem")
    connection.keyfile = None

    with pytest.raises(ValueError, match="both"):
        ClientConfig(connection=connection)
