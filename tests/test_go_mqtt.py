from __future__ import annotations

import asyncio
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


GO_CLIENT_DIR = Path(__file__).parent / "support" / "go-mqtt-client"


async def async_magic() -> None:
    pass


MagicMock.__await__ = lambda _: async_magic().__await__()


def fail_or_skip(message: str) -> None:
    if os.environ.get("CI") == "true":
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="session")
def go_mqtt_client(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if shutil.which("go") is None:
        fail_or_skip("Go MQTT interoperability tests require go")

    binary = tmp_path_factory.mktemp("go-mqtt-client") / "go-mqtt-client"
    env = os.environ.copy()
    env.setdefault("GOPROXY", "off")
    result = subprocess.run(
        ["go", "build", "-o", str(binary), "."],
        cwd=GO_CLIENT_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        fail_or_skip(
            "Go MQTT interoperability tests require downloaded Go module dependencies. "
            "Run `go mod download` in tests/support/go-mqtt-client.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )
    return binary


async def run_go_mqtt_client(binary: Path, *args: str) -> subprocess.CompletedProcess[str]:
    proc = await asyncio.create_subprocess_exec(
        str(binary),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    completed = subprocess.CompletedProcess(
        args=[str(binary), *args],
        returncode=proc.returncode,
        stdout=stdout.decode(),
        stderr=stderr.decode(),
    )
    assert completed.returncode == 0, (
        f"Go MQTT client failed with {completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return completed


@pytest.mark.asyncio
async def test_go_mqtt_connect(broker: Broker, mock_plugin_manager: MagicMock, go_mqtt_client: Path) -> None:
    await run_go_mqtt_client(go_mqtt_client, "connect", "127.0.0.1", "1883", f"go-mqtt-{random.randint(0, 1000)}")
    await asyncio.sleep(0.1)

    broker.plugins_manager.fire_event.assert_called()
    assert broker.plugins_manager.fire_event.call_count > 2

    events = [c[0][0] for c in broker.plugins_manager.fire_event.call_args_list]
    assert BrokerEvents.CLIENT_CONNECTED in events
    assert BrokerEvents.CLIENT_DISCONNECTED in events


@pytest.mark.asyncio
async def test_go_mqtt_qos1(broker: Broker, mock_plugin_manager: MagicMock, go_mqtt_client: Path) -> None:
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe([("/go/qos1", QOS_1)])

    await run_go_mqtt_client(
        go_mqtt_client,
        "publish",
        "127.0.0.1",
        "1883",
        f"go-mqtt-{random.randint(0, 1000)}",
        "/go/qos1",
        "test message",
        "1",
    )

    message = await asyncio.wait_for(sub_client.deliver_message(), timeout=5)
    assert message is not None
    assert message.qos == 1
    assert message.topic == "/go/qos1"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_go_mqtt_qos2(broker: Broker, mock_plugin_manager: MagicMock, go_mqtt_client: Path) -> None:
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe([("/go/qos2", QOS_2)])

    await run_go_mqtt_client(
        go_mqtt_client,
        "publish",
        "127.0.0.1",
        "1883",
        f"go-mqtt-{random.randint(0, 1000)}",
        "/go/qos2",
        "test message",
        "2",
    )

    message = await asyncio.wait_for(sub_client.deliver_message(), timeout=5)
    assert message is not None
    assert message.qos == 2
    assert message.topic == "/go/qos2"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_go_mqtt_ws(go_mqtt_client: Path) -> None:
    path = Path("docs_test/test.amqtt.local.yaml")
    with path.open() as f:
        cfg: dict[str, Any] = yaml.load(f, Loader=Loader)
    broker = Broker(config=cfg)
    await broker.start()

    try:
        await run_go_mqtt_client(
            go_mqtt_client,
            "ws-publish",
            "ws://127.0.0.1:8080",
            "go-mqtt-websocket-client-1",
            "/qos2",
            "test message",
            "2",
            "4",
        )
    finally:
        await broker.shutdown()
