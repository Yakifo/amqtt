import asyncio
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)
logger = logging.getLogger(__name__)


from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_1


@pytest.fixture
def broker_config():
    return {
        "listeners": {
            "default": {
                "type": "tcp",
                "bind": "127.0.0.1:1884",  # Use non-standard port for testing
            },
        },
        "sys_interval": 0,
        "auth": {
            "allow-anonymous": True,
            "plugins": ["auth_anonymous"],
        },
        "topic-check": {"enabled": False},
    }


@pytest.fixture
def config_file(broker_config, tmp_path):
    config_path = tmp_path / "config.yaml"
    with config_path.open("w") as f:
        yaml.dump(broker_config, f)
    return str(config_path)


@pytest.fixture
async def broker(config_file):

    proc = subprocess.Popen(
        ["amqtt", "-c", config_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give broker time to start
    await asyncio.sleep(1)
    yield proc
    proc.terminate()
    proc.wait()


def test_cli_help_messages():
    """Test that help messages are displayed correctly."""
    env = os.environ.copy()
    env["NO_COLOR"] = '1'

    amqtt_path = "amqtt"
    output = subprocess.check_output([amqtt_path, "--help"], env=env, text=True)
    assert "Usage: amqtt" in output


    amqtt_sub_path = "amqtt_sub"
    output = subprocess.check_output([amqtt_sub_path, "--help"], env=env, text=True)
    assert "Usage: amqtt_sub" in output


    amqtt_pub_path = "amqtt_pub"
    output = subprocess.check_output([amqtt_pub_path, "--help"], env=env, text=True)
    assert "Usage: amqtt_pub" in output


def test_broker_version():
    """Test broker version command."""
    output = subprocess.check_output(["amqtt", "--version"])
    assert output.strip()


@pytest.mark.asyncio
async def test_broker_start_stop(config_file):
    """Test broker start and stop with config file."""
    proc = subprocess.Popen(
        ["amqtt", "-c", config_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give broker time to start
    await asyncio.sleep(1)
    
    # Verify broker is running by connecting a client
    client = MQTTClient()
    await client.connect("mqtt://127.0.0.1:1884")
    await client.disconnect()
    
    # Stop broker
    proc.terminate()
    proc.wait()


@pytest.mark.asyncio
async def test_publish_subscribe(broker):
    """Test pub/sub CLI tools with running broker."""

    # Create a temporary file with test message
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp.write("test message\n")
        tmp.write("another message\n")
        tmp_path = tmp.name

    # Start subscriber in background
    sub_proc = subprocess.Popen(
        [
            "amqtt_sub",
            "--url", "mqtt://127.0.0.1:1884",
            "-t", "test/topic",
            "-n", "2",  # Exit after 2 messages
            "--qos", "1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Give subscriber time to connect
    await asyncio.sleep(0.5)
    #
    # # Publish messages from file
    pub_proc = subprocess.run(
        [
            "amqtt_pub",
            "--url", "mqtt://127.0.0.1:1884",
            "-t", "test/topic",
            "-f", tmp_path,
            "--qos", "1",
        ],
        capture_output=True,
    )
    assert pub_proc.returncode == 0
    #
    # # Wait for subscriber to receive messages
    stdout, stderr = sub_proc.communicate(timeout=5)
    
    # Clean up temp file
    os.unlink(tmp_path)

    # Verify messages were received
    print(stdout.decode("utf-8"))
    assert "test message" in str(stdout)
    assert "another message" in str(stdout)
    assert sub_proc.returncode == 0


@pytest.mark.asyncio
async def test_pub_sub_retain(broker):
    """Test various pub/sub will retain options."""
    # Test publishing with retain flag
    pub_proc = subprocess.run(
        [
            "amqtt_pub",
            "--url", "mqtt://127.0.0.1:1884",
            "-t", "topic/test",
            "-m", "standard message",
            "--will-topic", "topic/retain",
            "--will-message", "last will message",
            "--will-retain",
        ],
        capture_output=True,
    )
    assert pub_proc.returncode == 0, f"publisher error code: {pub_proc.returncode}\n{pub_proc.stderr}"
    logger.debug("publisher succeeded")
    # Verify retained message is received by new subscriber
    sub_proc = subprocess.run(
        [
            "amqtt_sub",
            "--url", "mqtt://127.0.0.1:1884",
            "-t", "topic/retain",
            "-n", "1",
        ],
        capture_output=True,
    )
    assert sub_proc.returncode == 0, f"subscriber error code: {sub_proc.returncode}\n{sub_proc.stderr}"
    assert "last will message" in str(sub_proc.stdout)


@pytest.mark.asyncio
async def test_pub_errors():
    """Test error handling in pub/sub tools."""
    # Test connection to non-existent broker
    pub_proc = subprocess.run(
        [
            "amqtt_pub",
            "--url", "mqtt://127.0.0.1:9999",  # Wrong port
            "-t", "test/topic",
            "-m", "test",
        ],
        capture_output=True,
    )
    assert pub_proc.returncode != 0, f"publisher error code: {pub_proc.returncode}"
    assert "Connection failed" in str(pub_proc.stderr)


@pytest.mark.asyncio
async def test_sub_errors():
    # Test invalid URL format
    sub_proc = subprocess.run(
        [
            "amqtt_sub",
            "--url", "invalid://url",
            "-t", "test/topic",
        ],
        capture_output=True,
    )
    assert sub_proc.returncode != 0, f"subscriber error code: {sub_proc.returncode}"
