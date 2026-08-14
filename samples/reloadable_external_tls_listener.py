# ruff: file-ignore[implicit-namespace-package]
"""Run a broker behind a reloadable external TLS listener.

To generate local development credentials:

    openssl req -x509 -noenc -days 365 -newkey rsa:2048 \
      -keyout key.pem -out cert.pem \
      -subj "/CN=localhost" \
      -addext "subjectAltName = DNS:localhost,IP:127.0.0.1"
"""

import argparse
import asyncio
from collections.abc import Callable
import logging
from pathlib import Path
import ssl

from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig, ListenerConfig, ListenerType
from amqtt.contrib.reloadable_tls import ReloadableExternalTLSListener, create_server_ssl_context

logger = logging.getLogger(__name__)

MQTT_LISTENER_NAME = "default"


def build_broker_config() -> BrokerConfig:
    """Create a broker config with one external listener."""
    return BrokerConfig(
        listeners={
            MQTT_LISTENER_NAME: ListenerConfig(type=ListenerType.EXTERNAL),
        },
        plugins={
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {
                "allow_anonymous": True,
            },
        },
    )


def build_tls_context_factory(
    *,
    certfile: Path,
    keyfile: Path,
    cafile: Path | None = None,
    require_client_cert: bool = False,
) -> Callable[[], ssl.SSLContext]:
    """Return a factory that builds the current server TLS context."""

    def factory() -> ssl.SSLContext:
        return create_server_ssl_context(
            certfile=certfile,
            keyfile=keyfile,
            cafile=cafile,
            verify_mode=ssl.CERT_REQUIRED if require_client_cert else ssl.CERT_NONE,
        )

    return factory


def build_tls_listener(
    *,
    broker: Broker,
    host: str,
    port: int,
    certfile: Path,
    keyfile: Path,
    cafile: Path | None = None,
    require_client_cert: bool = False,
) -> ReloadableExternalTLSListener:
    """Create the reloadable external TLS listener for the broker."""
    return ReloadableExternalTLSListener(
        broker=broker,
        listener_name=MQTT_LISTENER_NAME,
        host=host,
        port=port,
        ssl_context_factory=build_tls_context_factory(
            certfile=certfile,
            keyfile=keyfile,
            cafile=cafile,
            require_client_cert=require_client_cert,
        ),
    )


async def reload_tls_material(
    listener: ReloadableExternalTLSListener,
    *,
    certfile: Path,
    keyfile: Path,
    cafile: Path | None = None,
    require_client_cert: bool = False,
) -> None:
    """Reload TLS material for future client handshakes."""
    await listener.reload(
        build_tls_context_factory(
            certfile=certfile,
            keyfile=keyfile,
            cafile=cafile,
            require_client_cert=require_client_cert,
        ),
    )


async def run(
    *,
    host: str,
    port: int,
    certfile: Path,
    keyfile: Path,
    cafile: Path | None,
    require_client_cert: bool,
) -> None:
    """Start the broker and reloadable TLS listener until cancelled."""
    broker = Broker(build_broker_config())
    listener = build_tls_listener(
        broker=broker,
        host=host,
        port=port,
        certfile=certfile,
        keyfile=keyfile,
        cafile=cafile,
        require_client_cert=require_client_cert,
    )

    await broker.start()
    try:
        await listener.start()
        logger.info("MQTT over TLS listening on %s:%s", host, listener.actual_port)

        # Certificate watchers can call reload_tls_material(listener, ...) after material changes.
        await asyncio.Future()
    finally:
        await listener.close()
        await broker.shutdown()


def main() -> None:
    """Parse CLI arguments and run the sample broker."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", help="host for the external TLS listener")
    parser.add_argument("--port", type=int, default=8883, help="port for the external TLS listener")
    parser.add_argument("--certfile", type=Path, required=True, help="server certificate chain PEM file")
    parser.add_argument("--keyfile", type=Path, required=True, help="server private key PEM file")
    parser.add_argument("--cafile", type=Path, default=None, help="CA PEM file for client certificate verification")
    parser.add_argument("--require-client-cert", action="store_true", help="require clients to present trusted certificates")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(
            run(
                host=args.host,
                port=args.port,
                certfile=args.certfile,
                keyfile=args.keyfile,
                cafile=args.cafile,
                require_client_cert=args.require_client_cert,
            ),
        )
    except KeyboardInterrupt:
        logger.info("Broker stopped")


if __name__ == "__main__":
    main()
