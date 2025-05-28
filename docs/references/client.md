# MQTTClient API

The `amqtt.client.MQTTClient` class implements the client part of MQTT protocol. It can be used to publish and/or subscribe MQTT message on a broker accessible on the network through TCP or websocket protocol, both secured or unsecured.

## Usage examples

### Subscriber

The example below shows how to write a simple MQTT client which subscribes a topic and prints every messages received from the broker:

```python
import logging
import asyncio

from amqtt.client import MQTTClient, ClientException
from amqtt.mqtt.constants import QOS_1, QOS_2

logger = logging.getLogger(__name__)

async def uptime_coro():
    C = MQTTClient()
    await C.connect('mqtt://test.mosquitto.org/')
    # Subscribe to '$SYS/broker/uptime' with QOS=1
    # Subscribe to '$SYS/broker/load/#' with QOS=2
    await C.subscribe([
            ('$SYS/broker/uptime', QOS_1),
            ('$SYS/broker/load/#', QOS_2),
         ])
    try:
        for i in range(1, 100):
            message = await C.deliver_message()
            packet = message.publish_packet
            print("%d:  %s => %s" % (i, packet.variable_header.topic_name, str(packet.payload.data)))
        await C.unsubscribe(['$SYS/broker/uptime', '$SYS/broker/load/#'])
        await C.disconnect()
    except ClientException as ce:
        logger.error("Client exception: %s" % ce)

if __name__ == '__main__':
    formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    asyncio.get_event_loop().run_until_complete(uptime_coro())
```

When executed, this script gets the default event loop and asks it to run the `uptime_coro` until it completes.
`uptime_coro` starts by initializing a `MQTTClient` instance.
The coroutine then calls `connect()` to connect to the broker, here `test.mosquitto.org`.
Once connected, the coroutine subscribes to some topics, and then wait for 100 messages. Each message received is simply written to output.
Finally, the coroutine unsubscribes from topics and disconnects from the broker.

### Publisher

The example below uses the `MQTTClient` class to implement a publisher.
This test publish 3 messages asynchronously to the broker on a test topic.
For the purposes of the test, each message is published with a different Quality Of Service.
This example also shows two methods for publishing messages asynchronously.

```python
import logging
import asyncio

from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

logger = logging.getLogger(__name__)

async def test_coro():
    C = MQTTClient()
    await C.connect('mqtt://test.mosquitto.org/')
    tasks = [
        asyncio.ensure_future(C.publish('a/b', b'TEST MESSAGE WITH QOS_0')),
        asyncio.ensure_future(C.publish('a/b', b'TEST MESSAGE WITH QOS_1', qos=QOS_1)),
        asyncio.ensure_future(C.publish('a/b', b'TEST MESSAGE WITH QOS_2', qos=QOS_2)),
    ]
    await asyncio.wait(tasks)
    logger.info("messages published")
    await C.disconnect()


async def test_coro2():
    try:
        C = MQTTClient()
        ret = await C.connect('mqtt://test.mosquitto.org:1883/')
        message = await C.publish('a/b', b'TEST MESSAGE WITH QOS_0', qos=QOS_0)
        message = await C.publish('a/b', b'TEST MESSAGE WITH QOS_1', qos=QOS_1)
        message = await C.publish('a/b', b'TEST MESSAGE WITH QOS_2', qos=QOS_2)
        #print(message)
        logger.info("messages published")
        await C.disconnect()
    except ConnectException as ce:
        logger.error("Connection failed: %s" % ce)
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=formatter)
    asyncio.get_event_loop().run_until_complete(test_coro())
    asyncio.get_event_loop().run_until_complete(test_coro2())
```

As usual, the script runs the publish code through the async loop. `test_coro()` and `test_coro2()` are ran in sequence.
Both do the same job. `test_coro()` publishes 3 messages in sequence. `test_coro2()` publishes the same message asynchronously.
The difference appears when looking at the sequence of MQTT messages sent.

`test_coro()` achieves:

```
amqtt/YDYY;NNRpYQSy3?o -out-> PublishPacket(ts=2015-11-11 21:54:48.843901, fixed=MQTTFixedHeader(length=28, flags=0x0), variable=PublishVariableHeader(topic=a/b, packet_id=None), payload=PublishPayload(data="b'TEST MESSAGE WITH QOS_0'"))
amqtt/YDYY;NNRpYQSy3?o -out-> PublishPacket(ts=2015-11-11 21:54:48.844152, fixed=MQTTFixedHeader(length=30, flags=0x2), variable=PublishVariableHeader(topic=a/b, packet_id=1), payload=PublishPayload(data="b'TEST MESSAGE WITH QOS_1'"))
amqtt/YDYY;NNRpYQSy3?o <-in-- PubackPacket(ts=2015-11-11 21:54:48.979665, fixed=MQTTFixedHeader(length=2, flags=0x0), variable=PacketIdVariableHeader(packet_id=1), payload=None)
amqtt/YDYY;NNRpYQSy3?o -out-> PublishPacket(ts=2015-11-11 21:54:48.980886, fixed=MQTTFixedHeader(length=30, flags=0x4), variable=PublishVariableHeader(topic=a/b, packet_id=2), payload=PublishPayload(data="b'TEST MESSAGE WITH QOS_2'"))
amqtt/YDYY;NNRpYQSy3?o <-in-- PubrecPacket(ts=2015-11-11 21:54:49.029691, fixed=MQTTFixedHeader(length=2, flags=0x0), variable=PacketIdVariableHeader(packet_id=2), payload=None)
amqtt/YDYY;NNRpYQSy3?o -out-> PubrelPacket(ts=2015-11-11 21:54:49.030823, fixed=MQTTFixedHeader(length=2, flags=0x2), variable=PacketIdVariableHeader(packet_id=2), payload=None)
amqtt/YDYY;NNRpYQSy3?o <-in-- PubcompPacket(ts=2015-11-11 21:54:49.092514, fixed=MQTTFixedHeader(length=2, flags=0x0), variable=PacketIdVariableHeader(packet_id=2), payload=None)
```

while `test_coro2()` runs:

```
amqtt/LYRf52W[56SOjW04 -out-> PublishPacket(ts=2015-11-11 21:54:48.466123, fixed=MQTTFixedHeader(length=28, flags=0x0), variable=PublishVariableHeader(topic=a/b, packet_id=None), payload=PublishPayload(data="b'TEST MESSAGE WITH QOS_0'"))
amqtt/LYRf52W[56SOjW04 -out-> PublishPacket(ts=2015-11-11 21:54:48.466432, fixed=MQTTFixedHeader(length=30, flags=0x2), variable=PublishVariableHeader(topic=a/b, packet_id=1), payload=PublishPayload(data="b'TEST MESSAGE WITH QOS_1'"))
amqtt/LYRf52W[56SOjW04 -out-> PublishPacket(ts=2015-11-11 21:54:48.466695, fixed=MQTTFixedHeader(length=30, flags=0x4), variable=PublishVariableHeader(topic=a/b, packet_id=2), payload=PublishPayload(data="b'TEST MESSAGE WITH QOS_2'"))
amqtt/LYRf52W[56SOjW04 <-in-- PubackPacket(ts=2015-11-11 21:54:48.613062, fixed=MQTTFixedHeader(length=2, flags=0x0), variable=PacketIdVariableHeader(packet_id=1), payload=None)
amqtt/LYRf52W[56SOjW04 <-in-- PubrecPacket(ts=2015-11-11 21:54:48.661073, fixed=MQTTFixedHeader(length=2, flags=0x0), variable=PacketIdVariableHeader(packet_id=2), payload=None)
amqtt/LYRf52W[56SOjW04 -out-> PubrelPacket(ts=2015-11-11 21:54:48.661925, fixed=MQTTFixedHeader(length=2, flags=0x2), variable=PacketIdVariableHeader(packet_id=2), payload=None)
amqtt/LYRf52W[56SOjW04 <-in-- PubcompPacket(ts=2015-11-11 21:54:48.713107, fixed=MQTTFixedHeader(length=2, flags=0x0), variable=PacketIdVariableHeader(packet_id=2), payload=None)
```

Both coroutines have the same results except that `test_coro2()` manages messages flow in parallel which may be more efficient.


### Client configuration

The `MQTTClient` class's `__init__` method accepts a `config` parameter which allows setup of default and custom behaviors.

Details on the `config` parameter structure is a dictionary whose structure is identical to yaml formatted file[^1]
used by the included broker script: [client configuration](client_config.md)

::: amqtt.client.MQTTClient

[^1]: See [PyYAML](http://pyyaml.org/wiki/PyYAMLDocumentation) for loading YAML files as Python dict.

