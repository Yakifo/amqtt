from __future__ import annotations

from typing import TYPE_CHECKING, Any

from amqtt.errors import MQTTError
from amqtt.mqtt3.protocol.handler import ProtocolHandler
from amqtt.protocol import BrokerProtocolHandlerBase

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from amqtt.adapters import ReaderAdapter, WriterAdapter
    from amqtt.broker import BrokerContext
    from amqtt.plugins.manager import PluginManager
    from amqtt.session import Session

_CONNECT_NOT_IMPLEMENTED = "MQTT 5 CONNECT handling is not implemented yet"
_PINGREQ_NOT_IMPLEMENTED = "MQTT 5 PINGREQ handling is not implemented yet"
_SUBSCRIBE_NOT_IMPLEMENTED = "MQTT 5 SUBSCRIBE handling is not implemented yet"
_UNSUBSCRIBE_NOT_IMPLEMENTED = "MQTT 5 UNSUBSCRIBE handling is not implemented yet"
_SUBACK_NOT_IMPLEMENTED = "MQTT 5 SUBACK handling is not implemented yet"
_UNSUBACK_NOT_IMPLEMENTED = "MQTT 5 UNSUBACK handling is not implemented yet"
_CONNACK_NOT_IMPLEMENTED = "MQTT 5 CONNACK handling is not implemented yet"
_CONNECT_PARSING_NOT_IMPLEMENTED = "MQTT 5 CONNECT parsing is not implemented yet"


class BrokerProtocolHandler(
    BrokerProtocolHandlerBase["BrokerContext"],
    ProtocolHandler["BrokerContext"],
):
    """Broker protocol handler selected for MQTT 5.0 connections."""

    def __init__(
        self,
        plugins_manager: PluginManager[BrokerContext],
        session: Session | None = None,
        loop: AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(plugins_manager, session, loop)
        self._init_broker_handler_state()

    async def start(self) -> None:
        await ProtocolHandler.start(self)
        self._start_broker_handler()

    async def stop(self) -> None:
        await ProtocolHandler.stop(self)
        self._stop_broker_handler()

    def handle_write_timeout(self) -> None:
        pass

    def handle_read_timeout(self) -> None:
        pass

    async def handle_connect(self, _connect: Any) -> None:
        raise MQTTError(_CONNECT_NOT_IMPLEMENTED)

    async def handle_pingreq(self, _pingreq: Any) -> None:
        raise MQTTError(_PINGREQ_NOT_IMPLEMENTED)

    async def handle_subscribe(self, _subscribe: Any) -> None:
        raise MQTTError(_SUBSCRIBE_NOT_IMPLEMENTED)

    async def handle_unsubscribe(self, _unsubscribe: Any) -> None:
        raise MQTTError(_UNSUBSCRIBE_NOT_IMPLEMENTED)

    async def mqtt_acknowledge_subscription(self, _packet_id: int, _return_codes: list[int]) -> None:
        raise MQTTError(_SUBACK_NOT_IMPLEMENTED)

    async def mqtt_acknowledge_unsubscription(self, _packet_id: int) -> None:
        raise MQTTError(_UNSUBACK_NOT_IMPLEMENTED)

    async def mqtt_connack_authorize(self, _authorize: bool) -> None:
        raise MQTTError(_CONNACK_NOT_IMPLEMENTED)

    @classmethod
    async def init_from_connect(
        cls,
        _reader: ReaderAdapter,
        _writer: WriterAdapter,
        _plugins_manager: PluginManager[BrokerContext],
        _loop: AbstractEventLoop | None = None,
    ) -> tuple[BrokerProtocolHandler, Session]:
        raise MQTTError(_CONNECT_PARSING_NOT_IMPLEMENTED)
