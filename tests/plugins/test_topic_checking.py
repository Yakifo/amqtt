# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

import pytest

from amqtt.plugins.manager import BaseContext
from amqtt.plugins.topic_checking import BaseTopicPlugin, TopicTabooPlugin, TopicAccessControlListPlugin


class DummyLogger(object):
    def __init__(self):
        self.messages = []

    def warning(self, *args, **kwargs):
        self.messages.append((args, kwargs))


@pytest.mark.asyncio
async def test_base_no_config():
    """
    Check BaseTopicPlugin returns false if no topic-check is present.
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {}

    plugin = BaseTopicPlugin(context)
    assert plugin.topic_filtering() is False

    # Should have printed a couple of warnings
    assert len(context.logger.messages) == 2
    assert context.logger.messages[0] == (
            ("'topic-check' section not found in context configuration",),
            {}
    )
    assert context.logger.messages[1] == (
            ("'auth' section not found in context configuration",),
            {}
    )


@pytest.mark.asyncio
async def test_base_empty_config():
    """
    Check BaseTopicPlugin returns false if topic-check is empty.
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {
            'topic-check': {}
    }

    plugin = BaseTopicPlugin(context)
    assert plugin.topic_filtering() is False

    # Should NOT have printed warnings
    assert len(context.logger.messages) == 1
    assert context.logger.messages[0] == (
            ("'auth' section not found in context configuration",),
            {}
    )


@pytest.mark.asyncio
async def test_base_enabled_config():
    """
    Check BaseTopicPlugin returns true if enabled.
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {
            'topic-check': {
                'enabled': True
            }
    }

    plugin = BaseTopicPlugin(context)
    assert plugin.topic_filtering() is True

    # Should NOT have printed warnings
    assert len(context.logger.messages) == 0
