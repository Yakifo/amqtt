from collections.abc import MutableMapping
from dataclasses import dataclass, fields, is_dataclass
import json
from typing import Any

from amqtt.contrib.shadows.states import MetaTimestamp, ShadowOperation, State, StateDocument


def asdict_no_none(obj: Any) -> Any:
    """Create dictionary from dataclass, but eliminate any key set to `None`."""
    if is_dataclass(obj):
        result = {}
        for f in fields(obj):
            value = getattr(obj, f.name)
            if value is not None:
                result[f.name] = asdict_no_none(value)
        return result
    if isinstance(obj, list):
        return [asdict_no_none(item) for item in obj if item is not None]
    if isinstance(obj, dict):
        return {
            key: asdict_no_none(value)
            for key, value in obj.items()
            if value is not None
        }
    return obj


def create_shadow_topic(device_id: str, shadow_name: str, message_op: "ShadowOperation") -> str:
    """Create a shadow topic for message type."""
    return f"$shadow/{device_id}/{shadow_name}/{message_op}"


class ShadowMessage:
    def to_message(self) -> bytes:
        return json.dumps(asdict_no_none(self)).encode("utf-8")

@dataclass
class GetAcceptedMessage(ShadowMessage):
    state: State[dict[str, Any]]
    metadata: State[MetaTimestamp]
    timestamp: int
    version: int

    @staticmethod
    def topic(device_id: str, shadow_name: str) -> str:
        return create_shadow_topic(device_id, shadow_name, ShadowOperation.GET_ACCEPT)

@dataclass
class GetRejectedMessage(ShadowMessage):
    code: int
    message: str
    timestamp: int | None = None

    @staticmethod
    def topic(device_id: str, shadow_name: str) -> str:
        return create_shadow_topic(device_id, shadow_name, ShadowOperation.GET_REJECT)

@dataclass
class UpdateAcceptedMessage(ShadowMessage):
    state: State[dict[str, Any]]
    metadata: State[MetaTimestamp]
    timestamp: int
    version: int

    @staticmethod
    def topic(device_id: str, shadow_name: str) -> str:
        return create_shadow_topic(device_id, shadow_name, ShadowOperation.UPDATE_ACCEPT)


@dataclass
class UpdateRejectedMessage(ShadowMessage):
    code: int
    message: str
    timestamp: int

    @staticmethod
    def topic(device_id: str, shadow_name: str) -> str:
        return create_shadow_topic(device_id, shadow_name, ShadowOperation.UPDATE_REJECT)

@dataclass
class UpdateDeltaMessage(ShadowMessage):
    state: MutableMapping[str, Any]
    metadata: MutableMapping[str, Any]
    timestamp: int
    version: int

    @staticmethod
    def topic(device_id: str, shadow_name: str) -> str:
        return create_shadow_topic(device_id, shadow_name, ShadowOperation.UPDATE_DELTA)

class UpdateIotaMessage(UpdateDeltaMessage):
    """Same format, corollary name."""

    @staticmethod
    def topic(device_id: str, shadow_name: str) -> str:
        return create_shadow_topic(device_id, shadow_name, ShadowOperation.UPDATE_IOTA)

@dataclass
class UpdateDocumentMessage(ShadowMessage):
    previous: StateDocument
    current: StateDocument
    timestamp: int

    @staticmethod
    def topic(device_id: str, shadow_name: str) -> str:
        return create_shadow_topic(device_id, shadow_name, ShadowOperation.UPDATE_DOCUMENTS)
