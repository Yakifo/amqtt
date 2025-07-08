import pytest
from amqtt.errors import AMQTTError
from amqtt.mqtt.connack import ConnackPacket
from amqtt.mqtt.packet import MQTTFixedHeader, PUBLISH



def test_incorrect_fixed_header():
    header = MQTTFixedHeader(PUBLISH, 0x00)
    with pytest.raises(AMQTTError):
        _ = ConnackPacket(fixed=header)


@pytest.mark.parametrize("prop", [
    "return_code",
    "session_parent"
])
def test_empty_variable_header(prop):
    packet = ConnackPacket()

    with pytest.raises(ValueError):
        assert getattr(packet, prop) is not None

    with pytest.raises(ValueError):
        assert setattr(packet, prop, "a value")
