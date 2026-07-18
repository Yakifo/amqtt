
# -- build stage, install dependencies only using `uv`
FROM python:3.13-alpine@sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0 AS build
RUN apk add gcc python3-dev musl-dev linux-headers
COPY requirements-build.txt /tmp/requirements-build.txt
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements-build.txt

WORKDIR /app

COPY . /app
RUN uv pip install --target=/deps .


# -- final image, copy dependencies and amqtt source
FROM python:3.13-alpine@sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0

WORKDIR /app

COPY --from=build /deps /usr/local/lib/python3.13/site-packages/

COPY ./amqtt/scripts/default_broker.yaml /app/conf/broker.yaml

EXPOSE 1883

ENV PATH="/usr/local/lib/python3.13/site-packages/bin:$PATH"

# Run `amqtt` when the container launches
CMD ["amqtt", "-c", "/app/conf/broker.yaml"]
