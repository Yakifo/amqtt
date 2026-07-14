from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import random
import shutil
import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml
from yaml import Loader

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.events import BrokerEvents
from amqtt.mqtt.constants import QOS_1, QOS_2

logger = logging.getLogger(__name__)

MQTTJS_CWD = Path(__file__).resolve().parent.parent / "docs_test"


async def async_magic() -> None:
    pass


MagicMock.__await__ = lambda _: async_magic().__await__()

MQTTJS_RUNNER = """
const mqtt = require("mqtt");

const settings = JSON.parse(process.argv[1]);

let client;
let finished = false;

function finish(code, message) {
  if (finished) {
    return;
  }
  finished = true;
  clearTimeout(timeout);
  if (message) {
    console.error(message);
  }
  if (client) {
    client.end(true);
  }
  setTimeout(() => process.exit(code), 0);
}

function publish(topic, payload, qos) {
  return new Promise((resolve, reject) => {
    client.publish(topic, payload, { qos }, (error) => {
      if (error) {
        reject(error);
      } else {
        resolve();
      }
    });
  });
}

const timeout = setTimeout(() => {
  finish(1, `Timed out after ${settings.timeoutMs}ms`);
}, settings.timeoutMs);

client = mqtt.connect(settings.url, {
  clientId: settings.clientId,
  protocolVersion: 4,
  reconnectPeriod: 0,
  connectTimeout: settings.connectTimeoutMs,
  clean: true,
});

client.on("error", (error) => {
  finish(1, error.stack || error.message);
});

client.on("connect", async () => {
  try {
    if (settings.action === "publish") {
      for (const message of settings.messages) {
        await publish(message.topic, message.payload, message.qos);
      }
    }

    client.end(false, {}, () => finish(0));
  } catch (error) {
    finish(1, error.stack || error.message);
  }
});
"""


def _mqttjs_unavailable_reason() -> str | None:
    if shutil.which("node") is None:
        return "mqtt.js tests require node"

    result = subprocess.run(
        ["node", "-e", "require('mqtt')"],
        cwd=MQTTJS_CWD,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return (
            "mqtt.js tests require the mqtt package in docs_test/node_modules\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return None


@pytest.fixture(autouse=True)
def require_mqttjs() -> None:
    reason = _mqttjs_unavailable_reason()
    if reason is None:
        return
    if os.environ.get("CI") == "true":
        pytest.fail(reason)
    pytest.skip(reason)


async def run_mqttjs(settings: dict[str, Any]) -> None:
    settings.setdefault("timeoutMs", 5000)
    settings.setdefault("connectTimeoutMs", 3000)

    result = await asyncio.to_thread(
        subprocess.run,
        ["node", "-e", MQTTJS_RUNNER, json.dumps(settings)],
        cwd=MQTTJS_CWD,
        capture_output=True,
        text=True,
        timeout=(settings["timeoutMs"] / 1000) + 2,
        check=False,
    )

    if result.returncode != 0:
        raise AssertionError(
            f"mqtt.js client exited with {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )


@pytest.mark.asyncio
async def test_mqttjs_connect(broker: Broker, mock_plugin_manager: MagicMock) -> None:
    client_id = f"mqttjs-{random.randint(0, 1000)}"

    await run_mqttjs(
        {
            "action": "connect",
            "url": "mqtt://localhost:1883",
            "clientId": client_id,
        },
    )
    await asyncio.sleep(0.1)

    broker.plugins_manager.fire_event.assert_called()
    assert broker.plugins_manager.fire_event.call_count > 2

    events = [c[0][0] for c in broker.plugins_manager.fire_event.call_args_list]
    assert BrokerEvents.CLIENT_CONNECTED in events
    assert BrokerEvents.CLIENT_DISCONNECTED in events


@pytest.mark.asyncio
async def test_mqttjs_qos1(broker: Broker, mock_plugin_manager: MagicMock) -> None:
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe([("/mqttjs/qos1", QOS_1)])

    await run_mqttjs(
        {
            "action": "publish",
            "url": "mqtt://localhost:1883",
            "clientId": f"mqttjs-{random.randint(0, 1000)}",
            "messages": [{"topic": "/mqttjs/qos1", "payload": "test message", "qos": 1}],
        },
    )

    message = await sub_client.deliver_message()
    assert message is not None
    assert message.qos == 1
    assert message.topic == "/mqttjs/qos1"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_mqttjs_qos2(broker: Broker, mock_plugin_manager: MagicMock) -> None:
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe([("/mqttjs/qos2", QOS_2)])

    await run_mqttjs(
        {
            "action": "publish",
            "url": "mqtt://localhost:1883",
            "clientId": f"mqttjs-{random.randint(0, 1000)}",
            "messages": [{"topic": "/mqttjs/qos2", "payload": "test message", "qos": 2}],
        },
    )

    message = await sub_client.deliver_message()
    assert message is not None
    assert message.qos == 2
    assert message.topic == "/mqttjs/qos2"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_mqttjs_ws() -> None:
    path = Path("docs_test/test.amqtt.local.yaml")
    with path.open() as f:
        cfg: dict[str, Any] = yaml.load(f, Loader=Loader)
    logger.warning(cfg)
    broker = Broker(config=cfg)
    await broker.start()

    try:
        await run_mqttjs(
            {
                "action": "publish",
                "url": "ws://127.0.0.1:8080",
                "clientId": "mqttjs_websocket_client_1",
                "messages": [
                    {"topic": "/qos2", "payload": "test message", "qos": 2},
                    {"topic": "/qos2", "payload": "test message", "qos": 2},
                    {"topic": "/qos2", "payload": "test message", "qos": 2},
                    {"topic": "/qos2", "payload": "test message", "qos": 2},
                ],
            },
        )
    finally:
        await broker.shutdown()
