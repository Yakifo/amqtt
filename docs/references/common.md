# Common API

This document describes `aMQTT` common API both used by [MQTT Client](client.md) and [Broker](broker.md).

## Reference

### ApplicationMessage

The `amqtt.session` module provides the following message classes:

#### ApplicationMessage

Base class for MQTT application messages.

#### IncomingApplicationMessage

Inherits from ApplicationMessage. Represents messages received from MQTT clients.

#### OutgoingApplicationMessage

Inherits from ApplicationMessage. Represents messages to be sent to MQTT clients.
