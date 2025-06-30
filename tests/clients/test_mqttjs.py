import asyncio
import logging
import subprocess
from pathlib import Path

import pytest

from amqtt.broker import Broker

logger = logging.getLogger(__name__)


def check_npm_install():

    try:
        result = subprocess.run(["node", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("Node is installed:", result.stdout.decode().strip())
    except FileNotFoundError:
        logger.error("Node is not installed")
        return False
    except subprocess.CalledProcessError:
        logger.error("Node command failed to run properly")
        return False

    cwd = Path(__file__).parent.resolve()

    try:
        result = subprocess.run(["npm", "install"], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("npm installed succeeded:", result.stdout.decode().strip())
        return True
    except FileNotFoundError:
        logger.error("npm is not installed")
        return False
    except subprocess.CalledProcessError:
        logger.error("npm install command installed")
        return False


# mark this test as xfail and don't run if npm can't install dependencies
@pytest.mark.asyncio
@pytest.mark.xfail(condition=not check_npm_install(), run=False, reason="npm is not installed")
async def test_client_mqttjs():

    broker = Broker()
    await broker.start()
    await asyncio.sleep(2)

    cwd = Path(__file__).parent.resolve()

    process = subprocess.Popen(["npm", "run", "test"], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    await asyncio.sleep(2)

    stdout, stderr = process.communicate()
    logger.debug(stdout.decode())
    logger.debug(stderr.decode())
    assert process.returncode == 0
    assert "ERROR" not in stderr.decode("utf-8")
    assert "Exception" not in stderr.decode("utf-8")

    await broker.shutdown()

