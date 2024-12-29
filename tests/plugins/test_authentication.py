import asyncio
import logging
from pathlib import Path
import unittest

from amqtt.plugins.authentication import AnonymousAuthPlugin, FileAuthPlugin
from amqtt.plugins.manager import BaseContext
from amqtt.session import Session

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)


class TestAnonymousAuthPlugin(unittest.TestCase):
    def setUp(self) -> None:
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()

    def test_allow_anonymous(self) -> None:
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {"auth": {"allow-anonymous": True}}
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
        s.password = "test"  # noqa: S105
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
        s.password = "wrong password"  # noqa: S105
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
        s.password = "some password"  # noqa: S105
        auth_plugin = FileAuthPlugin(context)
        ret = self.loop.run_until_complete(auth_plugin.authenticate(session=s))
        assert not ret
