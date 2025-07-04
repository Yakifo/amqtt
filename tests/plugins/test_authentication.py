import asyncio
import logging
from pathlib import Path
import unittest

import pytest

from amqtt.plugins.authentication import AnonymousAuthPlugin, FileAuthPlugin
from amqtt.contexts import BaseContext
from amqtt.plugins.base import BaseAuthPlugin
from amqtt.session import Session

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)


@pytest.mark.asyncio
async def test_base_no_config(logdog):
    """Check BaseTopicPlugin returns false if no topic-check is present."""
    with logdog() as pile:
        context = BaseContext()
        context.logger = logging.getLogger("testlog")
        context.config = {}

        plugin = BaseAuthPlugin(context)
        s = Session()
        authorised = await plugin.authenticate(session=s)
        assert authorised is False

        # Warning messages are only generated if using deprecated plugin configuration on initial load
        log_records = list(pile.drain(name="testlog"))
        assert len(log_records) == 1
        assert log_records[0].levelno == logging.WARNING
        assert log_records[0].message == "'auth' section not found in context configuration"


class TestAnonymousAuthPlugin(unittest.TestCase):
    def setUp(self) -> None:
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()

    def test_allow_anonymous_dict_config(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {"auth": {"allow-anonymous": True}}
        s = Session()
        s.username = ""
        auth_plugin = AnonymousAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert ret

    def test_allow_anonymous_dataclass_config(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = AnonymousAuthPlugin.Config(allow_anonymous=True)
        s = Session()
        s.username = ""
        auth_plugin = AnonymousAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert ret

    def test_disallow_anonymous(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {"auth": {"allow-anonymous": False}}
        s = Session()
        s.username = ""
        auth_plugin = AnonymousAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert not ret

    def test_allow_nonanonymous(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {"auth": {"allow-anonymous": False}}
        s = Session()
        s.username = "test"
        auth_plugin = AnonymousAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert ret


class TestFileAuthPlugin(unittest.TestCase):
    def setUp(self) -> None:
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()

    def test_allow(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {
            "auth": {
                "password-file": Path(__file__).parent / "passwd",
            },
        }
        s = Session()
        s.username = "user"
        s.password = "test"
        auth_plugin = FileAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert ret

    def test_wrong_password(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {
            "auth": {
                "password-file": Path(__file__).parent / "passwd",
            },
        }
        s = Session()
        s.username = "user"
        s.password = "wrong password"
        auth_plugin = FileAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert not ret

    def test_unknown_password(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {
            "auth": {
                "password-file": Path(__file__).parent / "passwd",
            },
        }
        s = Session()
        s.username = "some user"
        s.password = "some password"
        auth_plugin = FileAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert not ret
