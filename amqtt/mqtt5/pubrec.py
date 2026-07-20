"""MQTT 5.0 PUBREC packet (§3.5)."""
from __future__ import annotations

from amqtt.mqtt3.packet import PUBREC
from amqtt.mqtt5._ack import AcknowledgementPacket, AcknowledgementVariableHeader
from amqtt.mqtt5.property_ids import PACKET_PUBREC


class PubrecVariableHeader(AcknowledgementVariableHeader):
    """MQTT 5.0 PUBREC variable header."""

    PACKET_NAME = PACKET_PUBREC


class PubrecPacket(AcknowledgementPacket[PubrecVariableHeader]):
    """MQTT 5.0 PUBREC packet."""

    VARIABLE_HEADER = PubrecVariableHeader  # could be inferred, but explicitly set for readability
    PACKET_TYPE = PUBREC
    PACKET_NAME = PACKET_PUBREC
    EXPECTED_FLAGS = 0x00
