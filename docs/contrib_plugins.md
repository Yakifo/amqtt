# Contributed Plugins

Beyond the original set of plugins created for aMQTT, `amqtt.contrib` plugins have been
more recently developed and contributed to the amqtt code base. These plugins require extra
dependencies:

`pip install amqtt[contrib]`

### Session Persistence

`amqtt.plugins.persistence.SessionDBPlugin`

Plugin to store session information and retained topic messages in the event that the broker terminates abnormally.

This plugin requires additional dependencies:



**Configuration**

- `file` - *(string)* path & filename to store the session db. default: `amqtt.db`
- `clear_on_shutdown` *(bool)* if the broker shutdowns down normally, don't retain any information. default: `True`

```yaml
plugins:
  amqtt.plugins.persistence.SessionDBPlugin:
    file: 'amqtt.db'
    clear_on_shutdown: True
```
