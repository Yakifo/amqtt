import json
import sqlite3
from typing import Any

from amqtt.plugins.manager import BaseContext
from amqtt.session import Session


class SQLitePlugin:
    def __init__(self, context: BaseContext) -> None:
        self.context: BaseContext = context
        self.conn: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None
        self.db_file: str | None = None
        self.persistence_config: dict[str, Any]

        if (
            persistence_config := self.context.config.get("persistence") if self.context.config is not None else None
        ) is not None:
            self.persistence_config = persistence_config
            self.init_db()
        else:
            self.context.logger.warning("'persistence' section not found in context configuration")

    def init_db(self) -> None:
        self.db_file = self.persistence_config.get("file")
        if not self.db_file:
            self.context.logger.warning("'file' persistence parameter not found")
        else:
            try:
                self.conn = sqlite3.connect(self.db_file)
                self.cursor = self.conn.cursor()
                self.context.logger.info(f"Database file '{self.db_file}' opened")
            except Exception:
                self.context.logger.exception(f"Error while initializing database '{self.db_file}'")
        if self.cursor:
            self.cursor.execute(
                "CREATE TABLE IF NOT EXISTS session(client_id TEXT PRIMARY KEY, data BLOB)",
            )
            self.cursor.execute("PRAGMA table_info(session)")
            columns = {col[1] for col in self.cursor.fetchall()}
            required_columns = {"client_id", "data"}
            if not required_columns.issubset(columns):
                self.context.logger.error("Database schema for 'session' table is incompatible.")

    async def save_session(self, session: Session) -> None:
        if self.cursor and self.conn:
            dump: str = json.dumps(session, default=str)
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO session (client_id, data) VALUES (?, ?)",
                    (session.client_id, dump),
                )
                self.conn.commit()
            except Exception:
                self.context.logger.exception(f"Failed saving session '{session}'")

    async def find_session(self, client_id: str) -> Session | None:
        if self.cursor:
            row = self.cursor.execute(
                "SELECT data FROM session where client_id=?",
                (client_id,),
            ).fetchone()
            return json.loads(row[0]) if row else None
        return None

    async def del_session(self, client_id: str) -> None:
        if self.cursor and self.conn:
            try:
                exists = self.cursor.execute("SELECT 1 FROM session WHERE client_id=?", (client_id,)).fetchone()
                if exists:
                    self.cursor.execute("DELETE FROM session where client_id=?", (client_id,))
                    self.conn.commit()
            except Exception:
                self.context.logger.exception(f"Failed deleting session with client_id '{client_id}'")

    async def on_broker_post_shutdown(self) -> None:
        if self.conn:
            try:
                self.conn.close()
                self.context.logger.info(f"Database file '{self.db_file}' closed")
            except Exception:
                self.context.logger.exception("Error closing database connection")
            finally:
                self.conn = None
