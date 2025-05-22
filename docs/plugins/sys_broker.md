# Plugin: $SYS

Publishes, on a periodic basis, statistics about the broker

### Config Options

- `sys_interval` - int, seconds between updates

### Supported Topics

- `$SYS/broker/load/bytes/received` - payload: 'data` - payload: `data`,  int
- `$SYS/broker/load/bytes/sent` - payload: 'data` - payload: `data`,  int
- `$SYS/broker/messages/received` - payload: `data`, int
- `$SYS/broker/messages/sent` - payload: `data`, int
- `$SYS/broker/time` - payload: `data`,  int (current, epoch seconds)
- `$SYS/broker/uptime` - payload: `data`,  datetime (start)
- `$SYS/broker/uptime/formatted` - payload: `data`, int (seconds)
- `$SYS/broker/clients/connected` - payload: `data`, int
- `$SYS/broker/clients/disconnected` - payload: `data`, int
- `$SYS/broker/clients/maximum` - payload: `data`, int
- `$SYS/broker/clients/total` - payload: `data`, int
- `$SYS/broker/messages/inflight` - payload: `data`, int
- `$SYS/broker/messages/inflight/in` - payload: `data`, int
- `$SYS/broker/messages/inflight/out` - payload: `data`, int
- `$SYS/broker/messages/inflight/stored` - payload: `data`, int
- `$SYS/broker/messages/publish/received` - payload: `data`, int
- `$SYS/broker/messages/publish/sent` - payload: `data`, int
- `$SYS/broker/messages/retained/count` - payload: `data`, int
- `$SYS/broker/messages/subscriptions/count` - payload: `data`, int
