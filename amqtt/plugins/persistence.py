import warnings

from amqtt.broker import BrokerContext
from amqtt.plugins.base import BasePlugin


class SQLitePlugin(BasePlugin[BrokerContext]):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)
        warnings.warn("SQLitePlugin is deprecated, use amqtt.plugins.persistence.SessionDBPlugin", stacklevel=1)
