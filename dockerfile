FROM python:3.13-alpine

WORKDIR /app
COPY . /app

RUN pip install --upgrade uv
RUN uv pip install --system --no-cache .

COPY ./amqtt/scripts/default_broker.yaml /app/config/broker.yaml

EXPOSE 1883

# Run app.py when the container launches
CMD ["amqtt", "-c", "/app/config/broker.yaml"]
