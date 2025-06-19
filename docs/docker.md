# Containerization

`amqtt` library is available on [PyPI](https://pypi.python.org/pypi/amqtt), [GitHub](https://github.com/Yakifo/amqtt) and [Read the Docs](http://amqtt.readthedocs.org/).

Built from [Dockerfile](https://github.com/Yakifo/amqtt/blob/main/dockerfile), the default `aMQTT` broker is publicly available on [DockerHub](https://hub.docker.com/repository/docker/amqtt/amqtt).

## Launch

```shell
$ docker run -d -p 1883:1883 amqtt/amqtt:latest
```

## Configure and launch

The easiest way to provide a custom [aMQTT broker configuration](references/broker_config.md),
is to create a yaml file...

```shell
$ cp amqtt/scripts/default_broker.yaml broker.yaml
```

and create a docker compose file...

```yaml
services:
  amqtt:
    image: amqtt
    container_name: amqtt
    ports:
      - "1883:1883"
    volumes:
      - ./broker.yaml:/app/conf/broker.yaml
```

and launch with...

```shell
$ docker compose -d -f docker-compose.yaml up
```

