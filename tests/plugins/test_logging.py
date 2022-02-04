import pytest

import amqtt.plugins.logging


def test_EventLoggerPlugin_getattr():
    logger = amqtt.plugins.logging.EventLoggerPlugin(None)
    with pytest.raises(AttributeError) as exc:
        logger.foo

    assert "foo" in str(exc.value)
