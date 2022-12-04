# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.
# Required for type hints in classes that self reference for python < v3.10
from __future__ import annotations
from typing import Optional

from amqtt.mqtt.packet import MQTTPacket, MQTTFixedHeader, PINGRESP
from amqtt.errors import AMQTTException


class PingRespPacket(MQTTPacket):
    VARIABLE_HEADER = None
    PAYLOAD = None

    variable_header: None
    payload: None

    def __init__(self, fixed: Optional[MQTTFixedHeader] = None):
        if fixed is None:
            header = MQTTFixedHeader(PINGRESP, 0x00)
        else:
            if fixed.packet_type is not PINGRESP:
                raise AMQTTException(
                    "Invalid fixed packet type %s for PingRespPacket init"
                    % fixed.packet_type
                )
            header = fixed
        super().__init__(header)
        self.variable_header = None
        self.payload = None

    @classmethod
    def build(cls) -> PingRespPacket:
        return cls()
