import pytest
import logging

from amqtt.plugins.manager import BaseContext
from amqtt.plugins.topic_checking import (
    BaseTopicPlugin,
    TopicTabooPlugin,
    TopicAccessControlListPlugin,
    Action,
)
from amqtt.session import Session


# Base plug-in object


@pytest.mark.asyncio
async def test_base_no_config(logdog):
    """
    Check BaseTopicPlugin returns false if no topic-check is present.
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {}

        plugin = BaseTopicPlugin(context)
        authorised = plugin.topic_filtering()
        assert authorised is False

    # Should have printed a couple of warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 2
    assert log_records[0].levelno == logging.WARN
    assert (
        log_records[0].message
        == "'topic-check' section not found in context configuration"
    )

    assert log_records[1].levelno == logging.WARN
    assert log_records[1].message == "'auth' section not found in context configuration"
    assert pile.is_empty()


@pytest.mark.asyncio
async def test_base_empty_config(logdog):
    """
    Check BaseTopicPlugin returns false if topic-check is empty.
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {}}

        plugin = BaseTopicPlugin(context)
        authorised = plugin.topic_filtering()
        assert authorised is False

    # Should have printed just one warning
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 1
    assert log_records[0].levelno == logging.WARN
    assert log_records[0].message == "'auth' section not found in context configuration"


@pytest.mark.asyncio
async def test_base_disabled_config(logdog):
    """
    Check BaseTopicPlugin returns true if disabled. (it doesn't actually check)
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {"enabled": False}}

        plugin = BaseTopicPlugin(context)
        authorised = plugin.topic_filtering()
        assert authorised is True

    # Should NOT have printed warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 0


@pytest.mark.asyncio
async def test_base_enabled_config(logdog):
    """
    Check BaseTopicPlugin returns true if enabled.
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {"enabled": True}}

        plugin = BaseTopicPlugin(context)
        authorised = plugin.topic_filtering()
        assert authorised is True

    # Should NOT have printed warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 0


# Taboo plug-in


@pytest.mark.asyncio
async def test_taboo_empty_config(logdog):
    """
    Check TopicTabooPlugin returns false if topic-check absent.
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {}

        plugin = TopicTabooPlugin(context)
        assert (await plugin.topic_filtering()) is False

    # Should have printed a couple of warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 2
    assert log_records[0].levelno == logging.WARN
    assert (
        log_records[0].message
        == "'topic-check' section not found in context configuration"
    )
    assert log_records[1].levelno == logging.WARN
    assert log_records[1].message == "'auth' section not found in context configuration"


@pytest.mark.asyncio
async def test_taboo_disabled(logdog):
    """
    Check TopicTabooPlugin returns true if checking disabled.
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {"enabled": False}}

        session = Session()
        session.username = "anybody"

        plugin = TopicTabooPlugin(context)
        assert (
            await plugin.topic_filtering(session=session, topic="not/prohibited")
        ) is True

    # Should NOT have printed warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 0


@pytest.mark.asyncio
async def test_taboo_not_taboo_topic(logdog):
    """
    Check TopicTabooPlugin returns true if topic not taboo
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {"enabled": True}}

        session = Session()
        session.username = "anybody"

        plugin = TopicTabooPlugin(context)
        assert (
            await plugin.topic_filtering(session=session, topic="not/prohibited")
        ) is True

    # Should NOT have printed warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 0


@pytest.mark.asyncio
async def test_taboo_anon_taboo_topic(logdog):
    """
    Check TopicTabooPlugin returns false if topic is taboo and session is anonymous.
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {"enabled": True}}

        session = Session()
        session.username = ""

        plugin = TopicTabooPlugin(context)
        assert (
            await plugin.topic_filtering(session=session, topic="prohibited")
        ) is False

    # Should NOT have printed warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 0


@pytest.mark.asyncio
async def test_taboo_notadmin_taboo_topic(logdog):
    """
    Check TopicTabooPlugin returns false if topic is taboo and user is not "admin".
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {"enabled": True}}

        session = Session()
        session.username = "notadmin"

        plugin = TopicTabooPlugin(context)
        assert (
            await plugin.topic_filtering(session=session, topic="prohibited")
        ) is False

    # Should NOT have printed warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 0


@pytest.mark.asyncio
async def test_taboo_admin_taboo_topic(logdog):
    """
    Check TopicTabooPlugin returns true if topic is taboo and user is "admin".
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {"topic-check": {"enabled": True}}

        session = Session()
        session.username = "admin"

        plugin = TopicTabooPlugin(context)
        assert (
            await plugin.topic_filtering(session=session, topic="prohibited")
        ) is True

    # Should NOT have printed warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 0


# TopicAccessControlListPlugin tests


def test_topic_ac_not_match():
    """
    Test TopicAccessControlListPlugin.topic_ac returns false if topics do not match.
    """
    assert (
        TopicAccessControlListPlugin.topic_ac("a/topic/to/match", "a/topic/to/notmatch")
        is False
    )


def test_topic_ac_not_match_longer_acl():
    """
    Test TopicAccessControlListPlugin.topic_ac returns false if topics do not match and ACL topic is longer.
    """
    assert TopicAccessControlListPlugin.topic_ac("topic", "topic/is/longer") is False


def test_topic_ac_not_match_longer_rq():
    """
    Test TopicAccessControlListPlugin.topic_ac returns false if topics do not match and RQ topic is longer.
    """
    assert TopicAccessControlListPlugin.topic_ac("topic/is/longer", "topic") is False


def test_topic_ac_match_exact():
    """
    Test TopicAccessControlListPlugin.topic_ac returns true if topics match exactly.
    """
    assert TopicAccessControlListPlugin.topic_ac("exact/topic", "exact/topic") is True


def test_topic_ac_match_plus():
    """
    Test TopicAccessControlListPlugin.topic_ac correctly handles '+' wildcard.
    """
    assert (
        TopicAccessControlListPlugin.topic_ac(
            "a/topic/anything/value", "a/topic/+/value"
        )
        is True
    )


def test_topic_ac_match_hash():
    """
    Test TopicAccessControlListPlugin.topic_ac correctly handles '#' wildcard.
    """
    assert (
        TopicAccessControlListPlugin.topic_ac(
            "topic/prefix/and/suffix", "topic/prefix/#"
        )
        is True
    )


@pytest.mark.asyncio
async def test_taclp_empty_config(logdog):
    """
    Check TopicAccessControlListPlugin returns false if topic-check absent.
    """
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {}

        plugin = TopicAccessControlListPlugin(context)
        assert (await plugin.topic_filtering()) is False

    # Should have printed a couple of warnings
    log_records = list(pile.drain(name="testlog"))
    assert len(log_records) == 2
    assert (
        log_records[0].message
        == "'topic-check' section not found in context configuration"
    )
    assert log_records[1].message == "'auth' section not found in context configuration"


@pytest.mark.asyncio
async def test_taclp_true_disabled(logdog):
    """
    Check TopicAccessControlListPlugin returns true if topic checking is disabled.
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {"topic-check": {"enabled": False}}

    session = Session()
    session.username = "user"

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.publish, session=session, topic="a/topic"
    )
    assert authorised is True


@pytest.mark.asyncio
async def test_taclp_true_no_pub_acl(logdog):
    """
    Check TopicAccessControlListPlugin returns true if action=publish and no publish-acl given.
    (This is for backward-compatibility with existing installations.)
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {"topic-check": {"enabled": True}}

    session = Session()
    session.username = "user"

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.publish, session=session, topic="a/topic"
    )
    assert authorised is True


@pytest.mark.asyncio
async def test_taclp_false_sub_no_topic(logdog):
    """
    Check TopicAccessControlListPlugin returns false user there is no topic.
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {
        "topic-check": {
            "enabled": True,
            "acl": {"anotheruser": ["allowed/topic", "another/allowed/topic/#"]},
        }
    }

    session = Session()
    session.username = "user"

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.subscribe, session=session, topic=""
    )
    assert authorised is False


@pytest.mark.asyncio
async def test_taclp_false_sub_unknown_user(logdog):
    """
    Check TopicAccessControlListPlugin returns false user is not listed in ACL.
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {
        "topic-check": {
            "enabled": True,
            "acl": {"anotheruser": ["allowed/topic", "another/allowed/topic/#"]},
        }
    }

    session = Session()
    session.username = "user"

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.subscribe, session=session, topic="allowed/topic"
    )
    assert authorised is False


@pytest.mark.asyncio
async def test_taclp_false_sub_no_permission(logdog):
    """
    Check TopicAccessControlListPlugin returns false if "acl" does not list allowed topic.
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {
        "topic-check": {
            "enabled": True,
            "acl": {"user": ["allowed/topic", "another/allowed/topic/#"]},
        }
    }

    session = Session()
    session.username = "user"

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.subscribe, session=session, topic="forbidden/topic"
    )
    assert authorised is False


@pytest.mark.asyncio
async def test_taclp_true_sub_permission(logdog):
    """
    Check TopicAccessControlListPlugin returns true if "acl" lists allowed topic.
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {
        "topic-check": {
            "enabled": True,
            "acl": {"user": ["allowed/topic", "another/allowed/topic/#"]},
        }
    }

    session = Session()
    session.username = "user"

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.subscribe, session=session, topic="allowed/topic"
    )
    assert authorised is True


@pytest.mark.asyncio
async def test_taclp_true_pub_permission(logdog):
    """
    Check TopicAccessControlListPlugin returns true if "publish-acl" lists allowed topic for publish action.
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {
        "topic-check": {
            "enabled": True,
            "publish-acl": {"user": ["allowed/topic", "another/allowed/topic/#"]},
        }
    }

    session = Session()
    session.username = "user"

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.publish, session=session, topic="allowed/topic"
    )
    assert authorised is True


@pytest.mark.asyncio
async def test_taclp_true_anon_sub_permission(logdog):
    """
    Check TopicAccessControlListPlugin handles anonymous users.
    """
    context = BaseContext()
    context.logger = logging.getLogger("testlog")
    context.config = {
        "topic-check": {
            "enabled": True,
            "acl": {"anonymous": ["allowed/topic", "another/allowed/topic/#"]},
        }
    }

    session = Session()
    session.username = None

    plugin = TopicAccessControlListPlugin(context)
    authorised = await plugin.topic_filtering(
        action=Action.subscribe, session=session, topic="allowed/topic"
    )
    assert authorised is True
