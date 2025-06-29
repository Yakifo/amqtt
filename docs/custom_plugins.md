from dataclasses import dataclass

# Custom Plugins

With the aMQTT plugins framework, one can add additional functionality to the client or broker without
having to rewrite any of the core logic.

To create a custom plugin, subclass from `BasePlugin` (client or broker) or `BaseAuthPlugin` (broker only)
or `BaseTopicPlugin` (broker only).  Each custom plugin may define settings specific to itself by creating
a nested (or inner) `dataclass` named `Config` which declares each option and a default value (if applicable). A
plugin's configuration dataclass will be type-checked and made available from within the `self.context` instance variable.

```python
from dataclasses import dataclass, field
from amqtt.plugins.base import BasePlugin
from amqtt.contexts import BaseContext


class OneClassName(BasePlugin[BaseContext]):
    """This is a plugin with no functionality"""

    
class TwoClassName(BasePlugin[BaseContext]):
    """This is a plugin with configuration options."""
    def __init__(self, context: BaseContext):
        super().__init__(context)
        my_option_one: str = self.context.config.option1
        
    @dataclass
    class Config:
        option1: int
        option3: str = field(default="my_default_value")

```

This plugin class then should be added to the configuration file of the broker or client (or to the `config`
dictionary passed to the `Broker` or `MQTTClient`). 

```yaml
...
...
plugins:
  - module.submodule.file.OneClassName:
  - module.submodule.file.TwoClassName:
      option1: 123
```

??? warning "Deprecated: activating plugins using `EntryPoints`"
    With the aMQTT plugins framework, one can add additional functionality to the client or broker without
    having to rewrite any of the core logic. To define a custom list of plugins to be loaded, add this section
    to your `pyproject.toml`"

    ```toml
    [project.entry-points."mypackage.mymodule.plugins"]
    plugin_alias = "module.submodule.file:ClassName"
    ```

    Each plugin has access to the full configuration file through the provided `BaseContext` and can define its own
    variables to configure its behavior.

::: amqtt.plugins.base.BasePlugin

## Events

All plugins are notified of events if the `BasePlugin` subclass implements one or more of these methods:

### Client and Broker

- `async def on_mqtt_packet_sent(self, *, packet: MQTTPacket[MQTTVariableHeader, MQTTPayload[MQTTVariableHeader], MQTTFixedHeader], session: Session | None = None) -> None`
- `async def on_mqtt_packet_received(self, *, packet: MQTTPacket[MQTTVariableHeader, MQTTPayload[MQTTVariableHeader], MQTTFixedHeader], session: Session | None = None) -> None`

### Client Only

none

### Broker Only

- `async def on_broker_pre_start() -> None`
- `async def on_broker_post_start() -> None`
- `async def on_broker_pre_shutdown() -> None`
- `async def on_broker_post_shutdown() -> None`

- `async def on_broker_client_connected(self, client_id:str) -> None`
- `async def on_broker_client_disconnected(self, client_id:str) -> None`

- `async def on_broker_client_subscribed(self, client_id: str, topic: str, qos: int) -> None`
- `async def on_broker_client_unsubscribed(self, client_id: str, topic: str) -> None`

- `async def on_broker_message_received(self, client_id: str, message: ApplicationMessage) -> None`


## Authentication Plugins

In addition to receiving any of the event callbacks, a plugin which subclasses from `BaseAuthPlugin`
is used by the aMQTT `Broker` to determine if a connection from a client is allowed by 
implementing the `authenticate` method and returning `True` if the session is allowed or `False` otherwise.

::: amqtt.plugins.base.BaseAuthPlugin

## Topic Filter Plugins

In addition to receiving any of the event callbacks, a plugin which is subclassed from `BaseTopicPlugin`
is used by the aMQTT `Broker` to determine if a connected client can send (PUBLISH) or receive (SUBSCRIBE)
messages to a particular topic by implementing the `topic_filtering` method and returning `True` if allowed or
`False` otherwise.

::: amqtt.plugins.base.BaseTopicPlugin


!!! note
    A custom plugin class can subclass from both `BaseAuthPlugin` and `BaseTopicPlugin` as long it defines
    both the `authenticate` and `topic_filtering` method.
