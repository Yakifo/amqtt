"""MQTT 5.0 PUBREL packet (§3.6)."""
from __future__ import annotations

from amqtt.mqtt3.packet import PUBREL
from amqtt.mqtt5._ack import AcknowledgementPacket, AcknowledgementVariableHeader
from amqtt.mqtt5.property_ids import PACKET_PUBREL


class PubrelVariableHeader(AcknowledgementVariableHeader):
    """MQTT 5.0 PUBREL variable header."""

    PACKET_NAME = PACKET_PUBREL


class PubrelPacket(AcknowledgementPacket[PubrelVariableHeader]):
    """MQTT 5.0 PUBREL packet."""

    VARIABLE_HEADER = PubrelVariableHeader  # could be inferred, but explicitly set for readability
    PACKET_TYPE = PUBREL
    PACKET_NAME = PACKET_PUBREL
    EXPECTED_FLAGS = 0x02
