"""Plugin to determine authentication of clients with DB storage."""
from dataclasses import dataclass

import click

try:
    from enum import StrEnum
except ImportError:
    # support for python 3.10
    from enum import Enum
    class StrEnum(str, Enum):  #type: ignore[no-redef]
        pass

from .plugin import TopicAuthDBPlugin, UserAuthDBPlugin


class DBType(StrEnum):
    """Enumeration for supported relational databases."""

    MARIA = "mariadb"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


@dataclass
class DBInfo:
    """SQLAlchemy database information."""

    connect_str: str
    connect_port: int | None


_db_map = {
    DBType.MARIA: DBInfo("mysql+aiomysql", 3306),
    DBType.MYSQL: DBInfo("mysql+aiomysql", 3306),
    DBType.POSTGRESQL: DBInfo("postgresql+asyncpg", 5432),
    DBType.SQLITE: DBInfo("sqlite+aiosqlite", None)
}


def db_connection_str(db_type: DBType, db_username: str, db_host:str, db_port: int|None, db_filename: str) -> str:
    """Create sqlalchemy database connection string."""
    db_info = _db_map[db_type]
    if db_type == DBType.SQLITE:
        return f"{db_info.connect_str}:///{db_filename}"
    db_password = click.prompt("Enter the db password (press enter for none)", hide_input=True)
    pwd = f":{db_password}" if db_password else ""
    return f"{db_info.connect_str}://{db_username}:{pwd}@{db_host}:{db_port or db_info.connect_port}"


__all__ = ["DBType", "TopicAuthDBPlugin", "UserAuthDBPlugin", "db_connection_str"]
