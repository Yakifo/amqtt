import logging
import socket
import ssl
import threading
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

from amqtt.broker import Broker
from amqtt.contexts import (
    BrokerConfig,
    ClientConfig,
    ConnectionConfig,
    ListenerConfig,
    ListenerTLSVersion,
    ListenerType,
    TopicConfig,
    WillConfig,
)
from amqtt.errors import BrokerError

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


def test_broker_config_from_dict_casts_listener_max_tls_version() -> None:
    broker_config = BrokerConfig.from_dict(
        {
            "listeners": {
                "default": {
                    "bind": "127.0.0.1:8883",
                    "max_tls_version": "TLSv1_2",
                },
            },
        },
    )

    listener_config = broker_config.listeners["default"]
    assert listener_config.max_tls_version is ListenerTLSVersion.TLSV1_2


def test_broker_config_from_dict_rejects_invalid_max_tls_version() -> None:
    with pytest.raises(ValueError, match="incorrect"):
        _ = BrokerConfig.from_dict(
            {
                "listeners": {
                    "default": {
                        "bind": "127.0.0.1:8883",
                        "max_tls_version": "incorrect",
                    },
                },
            },
        )


def test_listener_config_normalizes_max_tls_version_string(tmp_path: Path) -> None:
    certfile = tmp_path / "cert.pem"
    keyfile = tmp_path / "key.pem"
    certfile.write_text("cert", encoding="utf-8")
    keyfile.write_text("key", encoding="utf-8")

    listener = ListenerConfig(
        certfile=certfile,
        keyfile=keyfile,
        max_tls_version="TLSv1_2",
    )

    assert listener.max_tls_version is ListenerTLSVersion.TLSV1_2


def test_listener_config_rejects_invalid_max_tls_version_string() -> None:
    with pytest.raises(ValueError, match="expected one of"):
        ListenerConfig(max_tls_version="bogus")


def test_listener_config_rejects_legacy_tls_max_tls_versions() -> None:
    with pytest.raises(ValueError, match="expected one of"):
        ListenerConfig(max_tls_version="TLSv1")


@pytest.mark.parametrize(
    ("max_tls_version", "tls_version"),
    [
        (ListenerTLSVersion.TLSV1_2, ssl.TLSVersion.TLSv1_2),
        (ListenerTLSVersion.TLSV1_3, ssl.TLSVersion.TLSv1_3),
    ],
)
def test_broker_ssl_context_applies_max_tls_version(
    rsa_keys: tuple[Path, Path],
    max_tls_version: ListenerTLSVersion,
    tls_version: ssl.TLSVersion,
) -> None:
    certfile, keyfile = rsa_keys
    listener = ListenerConfig(
        ssl=True,
        certfile=certfile,
        keyfile=keyfile,
        max_tls_version=max_tls_version,
    )

    ssl_context = Broker._create_ssl_context(listener)

    assert ssl_context.maximum_version == tls_version


def test_broker_ssl_context_default_max_tls_version_unchanged(rsa_keys: tuple[Path, Path]) -> None:
    certfile, keyfile = rsa_keys
    listener = ListenerConfig(ssl=True, certfile=certfile, keyfile=keyfile)
    default_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

    ssl_context = Broker._create_ssl_context(listener)

    assert ssl_context.maximum_version == default_ctx.maximum_version


def test_broker_ssl_context_invalid_max_tls_version_not_misreported_as_cert_error(
    rsa_keys: tuple[Path, Path],
) -> None:
    certfile, keyfile = rsa_keys
    listener = ListenerConfig(ssl=True, certfile=certfile, keyfile=keyfile)
    # Bypass __post_init__ normalization to prove lookup errors are attributed correctly.
    listener.max_tls_version = "bogus"  # type: ignore[assignment]

    with pytest.raises(BrokerError, match="Invalid listener max_tls_version") as exc_info:
        Broker._create_ssl_context(listener)

    assert "certfile" not in str(exc_info.value)


def test_broker_ssl_context_tls12_ceiling_rejects_tls13_only_client(rsa_keys: tuple[Path, Path]) -> None:
    certfile, keyfile = rsa_keys
    server_ctx = Broker._create_ssl_context(
        ListenerConfig(
            ssl=True,
            certfile=certfile,
            keyfile=keyfile,
            max_tls_version=ListenerTLSVersion.TLSV1_2,
        ),
    )

    client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_ctx.check_hostname = False
    client_ctx.verify_mode = ssl.CERT_NONE
    client_ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    client_ctx.maximum_version = ssl.TLSVersion.TLSv1_3

    listener_sock = socket.socket()
    listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener_sock.bind(("127.0.0.1", 0))
    listener_sock.listen(1)
    port = listener_sock.getsockname()[1]
    server_errors: list[BaseException] = []

    def accept_and_handshake() -> None:
        conn, _ = listener_sock.accept()
        try:
            with server_ctx.wrap_socket(conn, server_side=True) as tls_conn:
                tls_conn.do_handshake()
        except BaseException as exc:  # noqa: BLE001 - collect handshake failure for assertion
            server_errors.append(exc)
        finally:
            conn.close()

    thread = threading.Thread(target=accept_and_handshake)
    thread.start()
    try:
        client_sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        with pytest.raises(ssl.SSLError):
            with client_ctx.wrap_socket(client_sock, server_hostname="localhost") as tls_client:
                tls_client.do_handshake()
    finally:
        thread.join(timeout=5)
        listener_sock.close()

    assert server_errors
    assert any(isinstance(error, ssl.SSLError) for error in server_errors)


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

    with pytest.warns(DeprecationWarning, match="broker"):
        client_config = ClientConfig(broker=broker_connection)

    assert client_config.connection is broker_connection


def test_client_config_rejects_mismatched_connection_cert_and_key() -> None:
    connection = ConnectionConfig(certfile="client.pem", keyfile="client-key.pem")
    connection.keyfile = None

    with pytest.raises(ValueError, match="both"):
        ClientConfig(connection=connection)
