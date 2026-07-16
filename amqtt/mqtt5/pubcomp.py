"""MQTT 5.0 PUBCOMP packet (§3.7)."""
from __future__ import annotations

from amqtt.mqtt3.packet import PUBCOMP
from amqtt.mqtt5._ack import AcknowledgementPacket, AcknowledgementVariableHeader
from amqtt.mqtt5.property_ids import PACKET_PUBCOMP


class PubcompVariableHeader(AcknowledgementVariableHeader):
    """MQTT 5.0 PUBCOMP variable header."""

    PACKET_NAME = PACKET_PUBCOMP


class PubcompPacket(AcknowledgementPacket[PubcompVariableHeader]):
    """MQTT 5.0 PUBCOMP packet."""

    VARIABLE_HEADER = PubcompVariableHeader
    PACKET_TYPE = PUBCOMP
    PACKET_NAME = PACKET_PUBCOMP
    EXPECTED_FLAGS = 0x00
