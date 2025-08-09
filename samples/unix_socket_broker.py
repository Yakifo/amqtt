from amqtt.broker import Broker
from amqtt.contexts import BrokerConfig, ListenerConfig


async def main():

    cfg = BrokerConfig(
        listeners={
            'default': ListenerConfig(
                ListenerType.External
            )
        }
    )

    b = Broker()