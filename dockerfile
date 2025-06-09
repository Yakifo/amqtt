
# -- build stage, install dependencies only using `uv`
FROM python:3.13-alpine AS build

RUN pip install uv

WORKDIR /app

COPY . /app
RUN uv pip install --target=/deps .


# -- final image, copy dependencies and amqtt source
FROM python:3.13-alpine

WORKDIR /app

COPY --from=build /deps /usr/local/lib/python3.13/site-packages/

COPY ./amqtt/scripts/default_broker.yaml /app/conf/broker.yaml

EXPOSE 1883

ENV PATH="/usr/local/lib/python3.13/site-packages/bin:$PATH"

# Run `amqtt` when the container launches
CMD ["amqtt", "-c", "/app/conf/broker.yaml"]
