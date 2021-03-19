# Copyright (c) 2015 Nicolas JOUANIN
#
# See the file license.txt for copying permission.

import unittest
import logging
import os
import asyncio
from hbmqtt.plugins.manager import BaseContext
from hbmqtt.plugins.topic_checking import BaseTopicPlugin, TopicTabooPlugin
from hbmqtt.session import Session

formatter = (
    "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
)
logging.basicConfig(level=logging.DEBUG, format=formatter)


class TestTopicCheckingPlugin(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_taboo_topic(self):
        context = BaseContext()
        context.logger = logging.getLogger(__name__)
        context.config = {
            "topic-check": {
                "taboo": ["prohibited", "top-secret", "data/classified"],
                "taboo_command": 1,
            }
        }
        s = Session()
        s.username = "admin"
        taboo_topic_plugin = TopicTabooPlugin(context)
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="prohibited", command=1, session=s)
        )
        assert ret
        s.username = "normal-user"
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="prohibited", command=1, session=s)
        )
        assert ret == False
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="prohibited", command=0, session=s)
        )
        assert ret
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="allowed", command=1, session=s)
        )
        assert ret
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="allowed", command=0, session=s)
        )
        context.config["topic-check"]["taboo_command"] = None
        taboo_topic_plugin = TopicTabooPlugin(context)
        assert ret
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="prohibited", command=1, session=s)
        )
        assert ret == False
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="prohibited", command=0, session=s)
        )
        assert ret == False
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="allowed", command=1, session=s)
        )
        assert ret
        ret = self.loop.run_until_complete(
            taboo_topic_plugin.topic_filtering(topic="allowed", command=0, session=s)
        )
