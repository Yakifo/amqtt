from collections import Counter
from collections.abc import MutableMapping
from dataclasses import asdict, dataclass, field
import time
from typing import Any

from mergedeep import merge


class StateError(Exception):
    def __init__(self, msg: str = "'state' field is required") -> None:
        super().__init__(msg)


def create_meta(state: MutableMapping[str, Any], timestamp: int) -> dict[str, Any]:
    """Create meta data (timestamps) for each of the keys in 'state'."""
    metadata: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, dict):
            metadata[key] = create_meta(value, timestamp)
        elif value is None:
            metadata[key] = None
        else:
            metadata[key] = timestamp

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
class State:
    desired: MutableMapping[str, Any] = field(default_factory=dict)
    reported: MutableMapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "State":
        """Create state from dictionary."""
        return cls(
            desired=data.get("desired", {}),
            reported=data.get("reported", {})
        )

    def __bool__(self) -> bool:
        """Determine if state is empty."""
        return bool(self.desired) or bool(self.reported)

    def __add__(self, other: "State") -> "State":
        """Merge states together."""
        return State(
            desired=merge({}, self.desired, other.desired),
            reported=merge({}, self.reported, other.reported)
        )


@dataclass
class StateDocument:
    state: State = field(default_factory=State)
    meta: State = field(default_factory=State)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StateDocument":
        """Create state document from dictionary."""
        now = int(time.time())
        if data and "state" not in data:
            raise StateError

        state = State.from_dict(data.get("state", {}))
        meta = State(
            desired=create_meta(state.desired, now),
            reported=create_meta(state.reported, now)
        )

        return cls(state=state, meta=meta)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __post_init__(self) -> None:
        """Initialize meta data if not provided."""
        now = int(time.time())
        if not self.meta:
            self.meta = State(
                desired=create_meta(self.state.desired, now),
                reported=create_meta(self.state.reported, now),
            )

    def __add__(self, other: "StateDocument") -> "StateDocument":
        """Merge two state documents together."""
        return StateDocument(
            state=self.state + other.state,
            meta=self.meta + other.meta
        )
