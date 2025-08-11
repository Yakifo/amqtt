# Device Shadows Plugin

Device shadows provide a persistent, cloud-based representation of the state of a device,
even when the device is offline. This plugin tracks the desired and reported state of a client
and provides MQTT topic-based communication channels to retrieve and update a shadow.

Typically, this structure is used for MQTT IoT devices to communicate with a central application.

This plugin is patterned after [AWS's IoT Shadow](https://docs.aws.amazon.com/iot/latest/developerguide/iot-device-shadows.html) service.  

## How it works

All shadow states are associated with a `device id` and `name` and have the following structure:

```json
{
  "state": {
    "desired": {
      "property1": "value1"
    },
    "reported": {
      "property1": "value1"
    }
  },
  "metadata": {
    "desired": {
      "property1": {
        "timestamp": 1623855600
      }
    },
    "reported": {
      "property1": {
        "timestamp": 1623855602
      }
    }
  },
  "version": 10,
  "timestamp": 1623855602
}
```

The `state` is updated by messages to shadow topics and includes key/value pairs, where the value can be any valid
json object (int, string, dictionary, list, etc). `metadata` is automatically updated by the plugin based on when
the key/values were most recently updated. Both `state` and `metadata` are split between:

- desired: the intended state of a device
- reported: the actual state of a device

A client can update a part or all of the desired or reported state. On any update, the plugin:

- updates the 'state' portion of the shadow with any key/values provided in the update
- stores a version of the update
- tracks the timestamp of each key/value pair change
- sends messages that the shadow was updated 

## Typical usage

As mentioned above, this plugin is often used for MQTT IoT devices to communicate with a central application. The
app pushes updates to a device's 'desired' shadow state and the device can confirm the change was made by updating
the 'reported' state. With this sequence the 'desired' state matches the 'reported' state and the delta message is empty.

In most situations, the app only updates the 'desired' state and the device only updates the 'reported' state.

If online, the IoT device will receive and can act on that information immediately. If offline, the app doesn't need
to republish or retry a change 'command', waiting for an acknowledgement from the device. If a device is offline, it
simply retrieves the configuration changes when it comes back online.

Once a device receives its desired state, it should either (1) update its reported state to match the change in desired
or (2) if the desired state is invalid, clear that key/value from the desired state. The latter is the only case
when a device should update its own 'desired' state.  

For example, if the app sends a command to set the brightness of a device to 100 lumens, but the device only supports
a maximum of 80, it can send an update `'state': {'desired': {'lumens': null}}` to clear the invalid state.

The reported state can (and most likely will) include key/values that will never show up in the desired state. For 
example, the app might set the thermostat to 70 and the device reports both the configuration change of 70 to the
thermostat *and* the current temperature of the room.

```json
{ 
  "state": { 
      "desired": {
        "thermostat": 68
      },
      "reported": {
        "thermostat": 68,
        "temperature": 78
      }
  }
}
```

!!! note "desired and reported state structure"
    It is important that both the app and the device have the same understanding of the key/value
     state structure and units. Creating [JSON schemas](https://json-schema.org/) for desired and
     reported shadow states are very useful as it can provide a clear way of describing the schema.
     These schemas can also be used to generate [dataclasses](https://pypi.org/project/datamodel-code-generator/),
     [pojos](https://github.com/joelittlejohn/jsonschema2pojo) or [many other language constructs](https://json-schema.org/tools?query=&sortBy=name&sortOrder=ascending&groupBy=toolingTypes&licenses=&languages=&drafts=&toolingTypes=&environments=&showObsolete=false&supportsBowtie=false#schema-to-code) that
     can be easily included by both app and device to make state encoding and decoding consistent.

## Shadow state access

All shadows are addressed by using specific topics, all of which have the following base:

`$shadow/<device_id>/<shadow name>`

Clients send either `get` or `update` messages:

| Operation               | Topic                                                 | Direction | Payload                                             |
|-------------------------|-------------------------------------------------------|-----------|-----------------------------------------------------|
| **Update**              | `$shadow/{device_id}/{shadow_name}/update`            | →         | `{ "state": { "desired" or "reported": ... } }`     |
| **Get**                 | `$shadow/{device_id}/{shadow_name}/get`               | →         | Empty message triggers get accepted or rejected     |

Then clients can subscribe to any or all of these topics which receive messages issued by the plugin:

| Operation               | Topic                                                 | Direction | Payload                                             |
|-------------------------|-------------------------------------------------------|-----------|-----------------------------------------------------|
| **Update Accepted**     | `$shadow/{device_id}/{shadow_name}/update/accepted`   | ←         | Full updated document                               |
| **Update Rejected**     | `$shadow/{device_id}/{shadow_name}/update/rejected`   | ←         | Error message                                       |
| **Update Documents**    | `$shadow/{device_id}/{shadow_name}/update/documents`  | ←         | Full current & previous shadow documents            |
| **Get Accepted**        | `$shadow/{device_id}/{shadow_name}/get/accepted`      | ←         | Full shadow document                                |
| **Get Rejected**        | `$shadow/{device_id}/{shadow_name}/get/rejected`      | ←         | Error message                                       |
| **Delta**               | `$shadow/{device_id}/{shadow_name}/update/delta`      | ←         | Difference between desired and reported             |
| **Iota**                | `$shadow/{device_id}/{shadow_name}/update/iota`       | ←         | Difference between desired and reported, with nulls |

## Delta messages

While the 'accepted' and 'documents' messages carry the full desired and reported states, this plugin also generates
a 'delta' message - containing items in the desired state that are different from those items in the reported state. This 
topic optimizes for IoT devices which typically have lower bandwidth and not as powerful processing by (1) to reducing the
amount of data transmitted and (2) simplifying device implementation as it only needs to respond to differences.

While shadows are stateful since delta messages are only based on the desired and reported state and *not on the previous
and current state*. Therefore, it doesn't matter if an IoT device is offline and misses a delta message. When it comes
back online, the delta is identical.

This is also an improvement over a connection without the clean flag and QoS > 0. When an IoT device comes back online, bandwidth
isn't consumed and the IoT device does not have to process a backlog of messages to understand how it should behave.
For a setting -- such as volume -- that goes from 80 then to 91 and then to 60 while the device is offline, it will
only receive a single change that its volume should now be 60.


| Reported Shadow State                  | Desired Shadow State                     | Resulting Delta Message (`delta`)     |
|----------------------------------------|------------------------------------------|---------------------------------------|
| `{ "temperature": 70 }`                | `{ "temperature": 72 }`                  | `{ "temperature": 72 }`               |
| `{ "led": "off", "fan": "low" }`       | `{ "led": "on", "fan": "low" }`          | `{ "led": "on" }`                     |
| `{ "door": "closed" }`                 | `{ "door": "closed", "alarm": "armed" }` | `{ "alarm": "armed" }`                |
| `{ "volume": 10 }`                     | `{ "volume": 10 }`                       | *(no delta; states match)*            |
| `{ "brightness": 100 }`                | `{ "brightness": 80, "mode": "eco" }`    | `{ "brightness": 80, "mode": "eco" }` |
| `{ "levels": [1, 10, 4]}`              | `{"levels": [1, 4, 10]}`                 | `{"levels": [1, 4, 10]}`              | 
| `{ "brightness": 100, "mode": "eco" }` | `{ "brightness": 80 }`                   | `{ "brightness": 80}`                 |


## Iota messages

Typically, null values never show in any received update message as a null signals the removal of a key from the desired
or reported state. However, if the app removes a key from the desired state -- such as a piece of state that is no longer
needed or applicable -- the device won't receive any notification of this deletion in a delta messages.  

These messages are very similar to 'delta' messages as they also contain items in the desired state that are different from
those in the reported state; it *also* contains any items in the reported state that are *missing* from the desired
state (last row in table). 

| Reported Shadow State                  | Desired Shadow State                     | Resulting Delta Message (`delta`)       |
|----------------------------------------|------------------------------------------|-----------------------------------------|
| `{ "temperature": 70 }`                | `{ "temperature": 72 }`                  | `{ "temperature": 72 }`                 |
| `{ "led": "off", "fan": "low" }`       | `{ "led": "on", "fan": "low" }`          | `{ "led": "on" }`                       |
| `{ "door": "closed" }`                 | `{ "door": "closed", "alarm": "armed" }` | `{ "alarm": "armed" }`                  |
| `{ "volume": 10 }`                     | `{ "volume": 10 }`                       | *(no delta; states match)*              |
| `{ "brightness": 100 }`                | `{ "brightness": 80, "mode": "eco" }`    | `{ "brightness": 80, "mode": "eco" }`   |
| `{ "levels": [1, 10, 4]}`              | `{"levels": [1, 4, 10]}`                 | `{"levels": [1, 4, 10]}`                |
| `{ "brightness": 100, "mode": "eco" }` | `{ "brightness": 80 }`                   | `{ "brightness": 80, "mode": null }`    |

## Configuration

::: amqtt.contrib.shadows.ShadowPlugin.Config
    options:
      show_source: false
      heading_level: 4
      extra:
        class_style: "simple"


## Security

Often a device only needs access to get/update and receive changes in its own shadow state. In  addition to the `ShadowPlugin`,
included is the `ShadowTopicAuthPlugin`. This allows (authorizes) a device to only subscribe, publish and receive its own topics.


::: amqtt.contrib.shadows.ShadowTopicAuthPlugin.Config
    options:
      show_source: false
      heading_level: 4
      extra:
        class_style: "simple"

!!! warning

       `ShadowTopicAuthPlugin` only handles topic authorization. Another plugin should be used to authenticate client device
        connections to the broker. See [file auth](packaged_plugins.md#password-file-auth-plugin),
        [http auth](http.md), [db auth](auth_db.md) or [certificate auth](cert.md) plugins. Or create your own:
        [auth plugins](custom_plugins.md#authentication-plugins): 
