"""MQTT 5.0 PUBACK packet (§3.4)."""
from __future__ import annotations

from amqtt.mqtt3.packet import PUBACK
from amqtt.mqtt5._ack import AcknowledgementPacket, AcknowledgementVariableHeader
from amqtt.mqtt5.property_ids import PACKET_PUBACK


class PubackVariableHeader(AcknowledgementVariableHeader):
    """MQTT 5.0 PUBACK variable header."""

    PACKET_NAME = PACKET_PUBACK


class PubackPacket(AcknowledgementPacket[PubackVariableHeader]):
    """MQTT 5.0 PUBACK packet."""

    VARIABLE_HEADER = PubackVariableHeader
    PACKET_TYPE = PUBACK
    PACKET_NAME = PACKET_PUBACK
    EXPECTED_FLAGS = 0x00
