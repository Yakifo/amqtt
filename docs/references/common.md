# Common API

This document describes `aMQTT` common API both used by [MQTT Client](client.md) and [Broker](broker.md).

## Session

Represents MQTT client connection state shared by broker, client, and plugins.

::: amqtt.session.Session
    options:
      heading_level: 3

## ApplicationMessage

::: amqtt.session.ApplicationMessage
    options:
      heading_level: 3

## IncomingApplicationMessage

Represents messages received from MQTT clients.

::: amqtt.session.IncomingApplicationMessage
    options:
      heading_level: 3


## OutgoingApplicationMessage

Inherits from ApplicationMessage. Represents messages to be sent to MQTT clients.

::: amqtt.session.OutgoingApplicationMessage
    options:
      heading_level: 3
