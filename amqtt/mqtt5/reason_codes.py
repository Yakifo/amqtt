"""MQTT 5.0 reason codes (§2.4)."""
from __future__ import annotations

from enum import IntEnum


class ReasonCode(IntEnum):
    """MQTT 5.0 Reason Code values.

    Only the success code is implemented here. Failure reason codes are tracked
    separately by the MQTT 5 reason-code issue.
    """

    SUCCESS = 0x00

    def is_error(self) -> bool:
        """Return whether this reason code represents an error."""
        return self >= 0x80

    @property
    def description(self) -> str:
        """Return a human-readable reason-code description."""
        return _DESCRIPTIONS[self]


_DESCRIPTIONS: dict[ReasonCode, str] = {
    ReasonCode.SUCCESS: "Success",
}
