# Broker API reference

The `amqtt.broker.Broker` class provides a complete MQTT 3.1.1 broker implementation. This class allows Python developers to embed a MQTT broker in their own applications.

## Usage example

The following example shows how to start a broker using the default configuration:

```python
--8<-- "samples/broker_simple.py"
```

This will start the broker and let it run until it is shutdown by `^c`.

## Reference

### Broker API

The `amqtt.broker` module provides the following key methods in the `Broker` class:

- `start()`: Starts the broker and begins serving
- `shutdown()`: Gracefully shuts down the broker


::: amqtt.broker.Broker
