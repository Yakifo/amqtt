# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

import pytest

from amqtt.plugins.manager import BaseContext
from amqtt.plugins.topic_checking import BaseTopicPlugin, TopicTabooPlugin, TopicAccessControlListPlugin
from amqtt.session import Session


class DummyLogger(object):
    def __init__(self):
        self.messages = []

    def warning(self, *args, **kwargs):
        self.messages.append((args, kwargs))


# Base plug-in object


@pytest.mark.asyncio
async def test_base_no_config():
    """
    Check BaseTopicPlugin returns false if no topic-check is present.
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {}

    plugin = BaseTopicPlugin(context)
    authorised = plugin.topic_filtering()
    assert authorised is False

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
    authorised = plugin.topic_filtering()
    assert authorised is False

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
    authorised = plugin.topic_filtering()
    assert authorised is True

    # Should NOT have printed warnings
    assert len(context.logger.messages) == 0


# Taboo plug-in

@pytest.mark.asyncio
async def test_taboo_empty_config():
    """
    Check TopicTabooPlugin returns false if topic-check absent.
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {}

    plugin = TopicTabooPlugin(context)
    authorised = await plugin.topic_filtering()
    assert authorised is False

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
async def test_taboo_not_taboo_topic():
    """
    Check TopicTabooPlugin returns true if topic not taboo
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {
            'topic-check': {
                'enabled': True
            }
    }

    session = Session()
    session.username = 'anybody'

    plugin = TopicTabooPlugin(context)
    authorised = await plugin.topic_filtering(
            session=session,
            topic='not/prohibited'
    )
    assert authorised is True

    # Should NOT have printed warnings
    assert len(context.logger.messages) == 0

@pytest.mark.asyncio
async def test_taboo_anon_taboo_topic():
    """
    Check TopicTabooPlugin returns false if topic is taboo and session is anonymous.
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {
            'topic-check': {
                'enabled': True
            }
    }

    session = Session()
    session.username = ''

    plugin = TopicTabooPlugin(context)
    authorised = await plugin.topic_filtering(
            session=session,
            topic='prohibited'
    )
    assert authorised is False

    # Should NOT have printed warnings
    assert len(context.logger.messages) == 0

@pytest.mark.asyncio
async def test_taboo_notadmin_taboo_topic():
    """
    Check TopicTabooPlugin returns false if topic is taboo and user is not "admin".
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {
            'topic-check': {
                'enabled': True
            }
    }

    session = Session()
    session.username = 'notadmin'

    plugin = TopicTabooPlugin(context)
    authorised = await plugin.topic_filtering(
            session=session,
            topic='prohibited'
    )
    assert authorised is False

    # Should NOT have printed warnings
    assert len(context.logger.messages) == 0

@pytest.mark.asyncio
async def test_taboo_admin_taboo_topic():
    """
    Check TopicTabooPlugin returns true if topic is taboo and user is "admin".
    """
    context = BaseContext()
    context.logger = DummyLogger()
    context.config = {
            'topic-check': {
                'enabled': True
            }
    }

    session = Session()
    session.username = 'admin'

    plugin = TopicTabooPlugin(context)
    authorised = await plugin.topic_filtering(
            session=session,
            topic='prohibited'
    )
    assert authorised is True

    # Should NOT have printed warnings
    assert len(context.logger.messages) == 0
