from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import MagicMock

import pytest

from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1, QOS_2


pytestmark = pytest.mark.extended

JAVA_CLIENT_SOURCE = Path(__file__).parent / "support" / "MqttInteropClient.java"
PAHO_JAR_GLOBS = (
    ".m2/repository/org/eclipse/paho/org.eclipse.paho.client.mqttv3/*/org.eclipse.paho.client.mqttv3-*.jar",
    ".gradle/caches/modules-2/files-2.1/org.eclipse.paho/org.eclipse.paho.client.mqttv3/*/*/org.eclipse.paho.client.mqttv3-*.jar",
)


def fail_or_skip(message: str) -> None:
    if os.environ.get("CI") == "true":
        pytest.fail(message)
    pytest.skip(message)


async def async_magic():
    pass


MagicMock.__await__ = lambda _: async_magic().__await__()


@pytest.fixture(scope="session")
def paho_mqtt_java_jar() -> Path:
    if jar_path := os.environ.get("PAHO_MQTT_JAR"):
        jar = Path(jar_path)
        if jar.is_file():
            return jar
        fail_or_skip(f"PAHO_MQTT_JAR does not exist: {jar}")

    home = Path.home()
    for pattern in PAHO_JAR_GLOBS:
        candidates = sorted(home.glob(pattern), reverse=True)
        if candidates:
            return candidates[0]

    fail_or_skip("Eclipse Paho Java MQTT client jar not found; set PAHO_MQTT_JAR to run these tests")


@pytest.fixture(scope="session")
def java_mqtt_client(tmp_path_factory: pytest.TempPathFactory, paho_mqtt_java_jar: Path) -> str:
    if shutil.which("java") is None or shutil.which("javac") is None:
        fail_or_skip("Java MQTT interoperability tests require java and javac")

    build_dir = tmp_path_factory.mktemp("java-mqtt-client")
    result = subprocess.run(
        ["javac", "-cp", str(paho_mqtt_java_jar), "-d", str(build_dir), str(JAVA_CLIENT_SOURCE)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"javac failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return os.pathsep.join((str(build_dir), str(paho_mqtt_java_jar)))


async def run_java_mqtt_client(classpath: str, *args: str) -> subprocess.CompletedProcess[str]:
    proc = await asyncio.create_subprocess_exec(
        "java",
        "-cp",
        classpath,
        "MqttInteropClient",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    completed = subprocess.CompletedProcess(
        args=["java", "-cp", classpath, "MqttInteropClient", *args],
        returncode=proc.returncode,
        stdout=stdout.decode(),
        stderr=stderr.decode(),
    )
    assert completed.returncode == 0, (
        f"Java MQTT client failed with {completed.returncode}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return completed


@pytest.mark.asyncio
async def test_java_mqtt_connect(broker, mock_plugin_manager, java_mqtt_client: str):
    await run_java_mqtt_client(java_mqtt_client, "connect", "127.0.0.1", "1883", "java-mqtt-connect")
    await asyncio.sleep(0.1)

    broker.plugins_manager.fire_event.assert_called()
    assert broker.plugins_manager.fire_event.call_count > 2


@pytest.mark.asyncio
async def test_java_mqtt_qos1(broker, mock_plugin_manager, java_mqtt_client: str):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe(
        [
            ("/java/qos1", QOS_1),
        ],
    )

    await run_java_mqtt_client(
        java_mqtt_client,
        "publish",
        "127.0.0.1",
        "1883",
        "java-mqtt-qos1",
        "/java/qos1",
        "test message",
        "1",
    )

    message = await asyncio.wait_for(sub_client.deliver_message(), timeout=5)
    assert message is not None
    assert message.qos == 1
    assert message.topic == "/java/qos1"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_java_mqtt_qos2(broker, mock_plugin_manager, java_mqtt_client: str):
    sub_client = MQTTClient()
    await sub_client.connect("mqtt://127.0.0.1")
    await sub_client.subscribe(
        [
            ("/java/qos2", QOS_2),
        ],
    )

    await run_java_mqtt_client(
        java_mqtt_client,
        "publish",
        "127.0.0.1",
        "1883",
        "java-mqtt-qos2",
        "/java/qos2",
        "test message",
        "2",
    )

    message = await asyncio.wait_for(sub_client.deliver_message(), timeout=5)
    assert message is not None
    assert message.qos == 2
    assert message.topic == "/java/qos2"
    assert message.data == b"test message"
    await sub_client.disconnect()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_java_mqtt_ws(broker, java_mqtt_client: str):
    await run_java_mqtt_client(
        java_mqtt_client,
        "ws-publish",
        "ws://127.0.0.1:8080/",
        "java-mqtt-ws",
        "/java/ws/qos2",
        "test message",
        "2",
        "4",
    )
    await asyncio.sleep(0.1)
