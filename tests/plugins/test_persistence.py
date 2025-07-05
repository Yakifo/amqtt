import asyncio
import logging
from pathlib import Path
import sqlite3
import unittest

import pytest

from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.contexts import BaseContext
from amqtt.mqtt.constants import QOS_0
from amqtt.plugins.persistence import SQLitePlugin
from amqtt.session import Session
from samples.client_publish_ssl import client

formatter = "[%(asctime)s] %(name)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=formatter)



@pytest.mark.asyncio
async def test_create_stored_session() -> None:

    cfg = {
        'listeners': {
            'default': {
                'type': 'tcp',
                'bind': '127.0.0.1:1883'
            }
        },
        'plugins': {
            'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow-anonymous': True},
            'amqtt.plugins.persistence.SessionDBPlugin': {}
        }
    }

    b = Broker(config=cfg)
    await b.start()
    await asyncio.sleep(1)

    c = MQTTClient(client_id='test_client1', config={'auto_reconnect':False})
    await c.connect(cleansession=False)
    await c.subscribe(
        [
            ('my/topic', QOS_0)
        ]
    )

    await c.disconnect()
    await asyncio.sleep(2)
    await b.shutdown()
    await asyncio.sleep(1)








"""

def test_create_tables(self) -> None:
    dbfile = Path(__file__).resolve().parent / "test.db"

    context = BaseContext()
    context.logger = logging.getLogger(__name__)
    context.config = {"persistence": {"file": str(dbfile)}}  # Ensure string path for config
    SQLitePlugin(context)

    try:
        conn = sqlite3.connect(str(dbfile))  # Convert Path to string for sqlite connection
        cursor = conn.cursor()
        rows = cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = [row[0] for row in rows]  # List comprehension for brevity
        assert "session" in tables
    finally:
        conn.close()

def test_save_session(self) -> None:
    dbfile = Path(__file__).resolve().parent / "test.db"

    context = BaseContext()
    context.logger = logging.getLogger(__name__)
    context.config = {"persistence": {"file": str(dbfile)}}  # Ensure string path for config
    sql_plugin = SQLitePlugin(context)

    s = Session()
    s.client_id = "test_save_session"

    self.loop.run_until_complete(sql_plugin.save_session(session=s))

    try:
        conn = sqlite3.connect(str(dbfile))  # Convert Path to string for sqlite connection
        cursor = conn.cursor()
        row = cursor.execute("SELECT client_id FROM session WHERE client_id = 'test_save_session'").fetchone()
        assert row is not None
        assert row[0] == s.client_id
    finally:
        conn.close()
"""