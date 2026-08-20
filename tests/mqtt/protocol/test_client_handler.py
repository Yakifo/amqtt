import asyncio
from typing import Any

import pytest

from amqtt.adapters import BufferWriter
from amqtt.errors import PublishAckTimeoutError
from amqtt.mqtt.constants import QOS_1
from amqtt.mqtt.protocol.client_handler import ClientProtocolHandler
from amqtt.mqtt.protocol.handler import ProtocolHandlerConfig
from amqtt.mqtt.puback import PubackPacket
from amqtt.session import OutgoingApplicationMessage, Session


class DummyPluginManager:
    def __init__(self) -> None:
        self.events: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def fire_event(self, *args: Any, **kwargs: Any) -> None:
        self.events.append((args, kwargs))


def make_session() -> Session:
    session = Session()
    session.client_id = "test-client"
    return session


def make_handler(qos1_puback_timeout: float) -> ClientProtocolHandler:
    handler = ClientProtocolHandler(
        DummyPluginManager(),
        make_session(),
        handler_config=ProtocolHandlerConfig(qos1_puback_timeout=qos1_puback_timeout),
    )
    handler.writer = BufferWriter()
    return handler


def make_qos1_message() -> OutgoingApplicationMessage:
    return OutgoingApplicationMessage(1, "/topic", QOS_1, b"test_data", False)


@pytest.mark.asyncio
async def test_client_qos1_puback_timeout_expires_and_cleans_state() -> None:
    qos1_timeout = 0.01
    handler = make_handler(qos1_timeout)
    message = make_qos1_message()

    started_at = asyncio.get_running_loop().time()
    with pytest.raises(PublishAckTimeoutError, match="Timeout waiting for PUBACK"):
        await asyncio.wait_for(handler._handle_qos1_message_flow(message), timeout=1)
    elapsed = asyncio.get_running_loop().time() - started_at

    assert elapsed >= qos1_timeout
    assert not handler._puback_waiters
    assert handler.session is not None
    assert not handler.session.inflight_out
    assert message.puback_packet is None


@pytest.mark.asyncio
async def test_client_qos1_puback_timeout_is_variable() -> None:
    async def publish_with_delayed_puback(
        qos1_timeout: float,
        puback_delay: float,
    ) -> OutgoingApplicationMessage:
        handler = make_handler(qos1_timeout)
        message = make_qos1_message()

        async def send_puback() -> None:
            while 1 not in handler._puback_waiters:
                await asyncio.sleep(0)
            await asyncio.sleep(puback_delay)
            await handler.handle_puback(PubackPacket.build(1))

        puback_task = asyncio.create_task(send_puback())
        try:
            await handler._handle_qos1_message_flow(message)
        finally:
            puback_task.cancel()
            await asyncio.gather(puback_task, return_exceptions=True)

        assert not handler._puback_waiters
        assert handler.session is not None
        assert not handler.session.inflight_out
        return message

    with pytest.raises(PublishAckTimeoutError, match="Timeout waiting for PUBACK"):
        await publish_with_delayed_puback(qos1_timeout=0.01, puback_delay=0.05)

    message = await publish_with_delayed_puback(qos1_timeout=0.2, puback_delay=0.05)
    assert message.puback_packet is not None
