from amqtt.broker import BrokerContext
from amqtt.plugins.base import BasePlugin

# intentional import error to test broker response
from pathlib import Pat  # noqa

class MockImportErrorPlugin(BasePlugin):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
