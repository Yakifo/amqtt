# Throttle Plugin

The `ThrottlePlugin` limits the rate of MQTT publications per client.

## Configuration

The plugin supports two rate-limiting algorithms:

- `token_bucket`: Allows messages according to a token bucket. The bucket refills over time and can hold a configurable number of tokens.
- `sliding_window`: Limits the number of messages published by a client within a moving time window.

| Option | Default | Description |
|---|---:|---|
| `algorithm` | `token_bucket` | Rate-limiting algorithm: `token_bucket` or `sliding_window`. |
| `message_limit` | `10` | Number of messages allowed per time window. |
| `time_window` | `4` | Length of the time window. |
| `max_tokens` | `20` | Maximum token bucket capacity. Only applies to `token_bucket`. |

## Example

```yaml
plugins:
  amqtt.contrib.throttle.plugin.ThrottlePlugin:
    algorithm: token_bucket
    message_limit: 10
    time_window: 4
    max_tokens: 20