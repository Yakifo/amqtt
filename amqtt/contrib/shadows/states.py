from collections import Counter
from collections.abc import MutableMapping
from dataclasses import dataclass, field

try:
    from enum import StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  # type: ignore[no-redef]
        pass
import time
from typing import Any, Generic, TypeVar

from mergedeep import merge

C = TypeVar("C", bound=Any)


class StateError(Exception):
    def __init__(self, msg: str = "'state' field is required") -> None:
        super().__init__(msg)


@dataclass
class MetaTimestamp:
    timestamp: int = 0

    def __eq__(self, other: object) -> bool:
        """Compare timestamps."""
        if isinstance(other, int):
            return self.timestamp == other
        if isinstance(other, self.__class__):
            return self.timestamp == other.timestamp
        msg = "needs to be int or MetaTimestamp"
        raise ValueError(msg)

    # numeric operations to make this dataclass transparent
    def __abs__(self) -> int:
        """Absolute timestamp."""
        return self.timestamp

    def __add__(self, other: int) -> int:
        """Add to a timestamp."""
        return self.timestamp + other

    def __sub__(self, other: int) -> int:
        """Subtract from a timestamp."""
        return self.timestamp - other

    def __mul__(self, other: int) -> int:
        """Multiply a timestamp."""
        return self.timestamp * other

    def __float__(self) -> float:
        """Convert timestamp to float."""
        return float(self.timestamp)

    def __int__(self) -> int:
        """Convert timestamp to int."""
        return int(self.timestamp)

    def __lt__(self, other: int) -> bool:
        """Compare timestamp."""
        return self.timestamp < other

    def __le__(self, other: int) -> bool:
        """Compare timestamp."""
        return self.timestamp <= other

    def __gt__(self, other: int) -> bool:
        """Compare timestamp."""
        return self.timestamp > other

    def __ge__(self, other: int) -> bool:
        """Compare timestamp."""
        return self.timestamp >= other


def create_metadata(state: MutableMapping[str, Any], timestamp: int) -> dict[str, Any]:
    """Create metadata (timestamps) for each of the keys in 'state'."""
    metadata: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, dict):
            metadata[key] = create_metadata(value, timestamp)
        elif value is None:
            metadata[key] = None
        else:
            metadata[key] = MetaTimestamp(timestamp)

    return metadata


def calculate_delta_update(desired: MutableMapping[str, Any],
                           reported: MutableMapping[str, Any],
                           depth: bool = True,
                           exclude_nones: bool = True,
                           ordered_lists: bool = True) -> dict[str, Any]:
    """Calculate state differences between desired and reported."""
    diff_dict = {}
    for key, value in desired.items():
        if value is None and exclude_nones:
            continue
        # if the desired has an element that the reported does not...
        if key not in reported:
            diff_dict[key] = value
        # if the desired has an element that's a list, but the list is
        elif isinstance(value, list) and not ordered_lists:
            if Counter(value) != Counter(reported[key]):
                diff_dict[key] = value
        elif isinstance(value, dict) and depth:
            # recurse, report when there is a difference
            obj_diff = calculate_delta_update(value, reported[key])
            if obj_diff:
                diff_dict[key] = obj_diff
        elif value != reported[key]:
            diff_dict[key] = value

    return diff_dict


def calculate_iota_update(desired: MutableMapping[str, Any], reported: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Calculate state differences between desired and reported (including missing keys)."""
    delta = calculate_delta_update(desired, reported, depth=False, exclude_nones=False)

    for key in reported:
        if key not in desired:
            delta[key] = None

    return delta


@dataclass
class State(Generic[C]):
    desired: MutableMapping[str, C] = field(default_factory=dict)
    reported: MutableMapping[str, C] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, C]) -> "State[C]":
        """Create state from dictionary."""
        return cls(
            desired=data.get("desired", {}),
            reported=data.get("reported", {})
        )

    def __bool__(self) -> bool:
        """Determine if state is empty."""
        return bool(self.desired) or bool(self.reported)

    def __add__(self, other: "State[C]") -> "State[C]":
        """Merge states together."""
        return State(
            desired=merge({}, self.desired, other.desired),
            reported=merge({}, self.reported, other.reported)
        )


@dataclass
class StateDocument:
    state: State[dict[str, Any]] = field(default_factory=State)
    metadata: State[MetaTimestamp] = field(default_factory=State)
    version: int | None = None  # only required when generating shadow messages
    timestamp: int | None = None  # only required when generating shadow messages

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StateDocument":
        """Create state document from dictionary."""
        now = int(time.time())
        if data and "state" not in data:
            raise StateError

        state = State.from_dict(data.get("state", {}))
        metadata = State(
            desired=create_metadata(state.desired, now),
            reported=create_metadata(state.reported, now)
        )

        return cls(state=state, metadata=metadata)

    def __post_init__(self) -> None:
        """Initialize meta data if not provided."""
        now = int(time.time())
        if not self.metadata:
            self.metadata = State(
                desired=create_metadata(self.state.desired, now),
                reported=create_metadata(self.state.reported, now),
            )

    def __add__(self, other: "StateDocument") -> "StateDocument":
        """Merge two state documents together."""
        return StateDocument(
            state=self.state + other.state,
            metadata=self.metadata + other.metadata
        )


class ShadowOperation(StrEnum):
    GET = "get"
    UPDATE = "update"
    GET_ACCEPT = "get/accepted"
    GET_REJECT = "get/rejected"
    UPDATE_ACCEPT = "update/accepted"
    UPDATE_REJECT = "update/rejected"
    UPDATE_DOCUMENTS = "update/documents"
    UPDATE_DELTA = "update/delta"
    UPDATE_IOTA = "update/iota"
