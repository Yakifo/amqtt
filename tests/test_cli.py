import asyncio
import logging
import os
import signal
import subprocess
import tempfile

import pytest
import yaml

from amqtt.mqtt.constants import QOS_0

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)
logger = logging.getLogger(__name__)


from amqtt.client import MQTTClient


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
def broker_config_file(broker_config, tmp_path):
    config_path = tmp_path / "broker.yaml"
    with config_path.open("w") as f:
        yaml.dump(broker_config, f)
    return str(config_path)


@pytest.fixture
async def broker(broker_config_file):

    proc = subprocess.Popen(
        ["amqtt", "-c", broker_config_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give broker time to start
    await asyncio.sleep(4)
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
async def test_broker_start_stop(broker_config_file):
    """Test broker start and stop with config file."""
    proc = subprocess.Popen(
        ["amqtt", "-c", broker_config_file],
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
async def test_pub_errors(client_config_file):
    """Test error handling in pub/sub tools."""
    # Test connection to non-existent broker
    cmd =         [
            "amqtt_pub",
            "--url", "mqtt://127.0.0.1:9999",  # Wrong port
            "-t", "test/topic",
            "-m", "test",
            "-c", client_config_file,
        ]

    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    logger.debug(f"Command: {cmd}")
    logger.debug(f"Stdout: {stdout.decode()}")
    logger.debug(f"Stderr: {stderr.decode()}")

    assert proc.returncode != 0, f"publisher error code: {proc.returncode}"
    assert "Connection failed" in str(stderr)


@pytest.mark.asyncio
async def test_sub_errors(client_config_file):
    # Test invalid URL format
    sub_proc = subprocess.run(
        [
            "amqtt_sub",
            "--url", "invalid://url",
            "-t", "test/topic",
            "-c", client_config_file
        ],
        capture_output=True,
    )
    assert sub_proc.returncode != 0, f"subscriber error code: {sub_proc.returncode}"


@pytest.fixture
def client_config():
    return {
        "keep_alive": 10,
        "ping_delay": 1,
        "default_qos": 0,
        "default_retain": False,
        "auto_reconnect": False,
        "will": {
            "topic": "test/will/topic",
            "message": "client ABC has disconnected",
            "qos": 0,
            "retain": False
        },
        "broker": {
            "uri": "mqtt://localhost:1884"
        }
    }


@pytest.fixture
def client_config_file(client_config, tmp_path):
    config_path = tmp_path / "client.yaml"
    with config_path.open("w") as f:
        yaml.dump(client_config, f)
    return str(config_path)


@pytest.mark.asyncio
async def test_pub_client_config(broker, client_config_file):
    await asyncio.sleep(1)
    cmd = [
            "amqtt_pub",
            "-t", "test/topic",
            "-m", "test",
            "-c", client_config_file
        ]
    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    logger.debug(f"Command: {cmd}")
    logger.debug(f"Stdout: {stdout.decode()}")
    logger.debug(f"Stderr: {stderr.decode()}")

    assert proc.returncode == 0, f"publisher error code: {proc.returncode}"


@pytest.mark.asyncio
async def test_pub_client_config_will(broker, client_config_file):

    # verifying client script functionality of will topic (publisher)
    # https://github.com/Yakifo/amqtt/issues/159
    await asyncio.sleep(1)
    client1 = MQTTClient(client_id="client1")
    await client1.connect('mqtt://localhost:1884')
    await  client1.subscribe([
        ("test/will/topic", QOS_0)
        ])

    cmd = ["amqtt_pub",
            "-t", "test/topic",
            "-m", "\"test of regular topic\"",
            "-c", client_config_file]

    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    logger.debug(f"Command: {cmd}")
    logger.debug(f"Stdout: {stdout.decode()}")
    logger.debug(f"Stderr: {stderr.decode()}")

    message = await client1.deliver_message(timeout_duration=1)
    assert message.topic == 'test/will/topic'
    assert message.data == b'client ABC has disconnected'
    await client1.disconnect()

@pytest.mark.asyncio
@pytest.mark.timeout(20)
async def test_sub_client_config_will(broker, client_config, client_config_file):

    # verifying client script functionality of will topic (subscriber)
    # https://github.com/Yakifo/amqtt/issues/159

    client1 = MQTTClient(client_id="client1")
    await client1.connect('mqtt://localhost:1884')
    await  client1.subscribe([
        ("test/will/topic", QOS_0)
        ])

    cmd = ["amqtt_sub",
            "-t", "test/topic",
            "-c", client_config_file,
            "-n", "1"]

    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await asyncio.sleep(2)

    # cause `amqtt_sub` to exit after receiving this one message
    await client1.publish("test/topic", b'my test message')


    # validate the 'will' message was received correctly
    message = await client1.deliver_message(timeout_duration=3)
    assert message.topic == 'test/will/topic'
    assert message.data == b'client ABC has disconnected'
    await client1.disconnect()


    stdout, stderr = await proc.communicate()
    logger.debug(f"Command: {cmd}")
    logger.debug(f"Stdout: {stdout.decode()}")
    logger.debug(f"Stderr: {stderr.decode()}")
    