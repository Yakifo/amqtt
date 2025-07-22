import asyncio
from dataclasses import dataclass
from enum import StrEnum
import logging
from pathlib import Path
from typing import Annotated

import passlib
from rich.prompt import Confirm, Prompt
import typer

from amqtt.contrib.auth_db.managers import UserManager
from amqtt.errors import MQTTError

logger = logging.getLogger(__name__)
user_app = typer.Typer(no_args_is_help=True)


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
    db_password = Prompt.ask("Enter the db password (press enter for none)", password=True)
    pwd = f":{db_password}" if db_password else ""
    return f"{db_info.connect_str}://{db_username}:{pwd}@{db_host}:{db_port or db_info.connect_port}"


@user_app.callback()
def main(
        ctx: typer.Context,
        db_type: Annotated[DBType, typer.Option("--db", "-d", help="db type", count=False)],
        db_username: Annotated[str, typer.Option("--username", "-u", help="db username")] | None = None,
        db_port: Annotated[int, typer.Option("--port", "-p", help="database port (defaults to db type)")] | None = None,
        db_host: Annotated[str, typer.Option("--host", "-h", help="database host")] = "localhost",
        db_filename: Annotated[str, typer.Option("--file", "-f", help="database file name (sqlite only)")] = "auth.db",
) -> None:
    """Command line interface to list, create, remove and add clients.

    Passwords are not allowed to be passed via the command line for security reasons. You will be prompted for database
    password (if applicable) and the client id's password.

    If you need to create users programmatically, see `amqtt.contrib.auth_db.managers.UserManager` which provides
    the underlying functionality to this command line interface.
    """
    if db_type == DBType.SQLITE and ctx.invoked_subcommand == "sync" and not Path(db_filename).exists():
        pass
    elif db_type == DBType.SQLITE and not Path(db_filename).exists():
        logger.error(f"SQLite option could not find '{db_filename}'")
        raise typer.Exit(code=1)
    elif db_type != DBType.SQLITE and not db_username:
        logger.error("DB access requires a username be provided.")
        raise typer.Exit(code=1)

    ctx.obj = {"type": db_type, "username": db_username, "host": db_host, "port": db_port, "filename": db_filename}


@user_app.command(name="sync")
def db_sync(ctx: typer.Context) -> None:
    """Create the table and schema for username and hashed password.

    Non-destructive if run multiple times. To clear the whole table, need to drop it manually.
    """
    async def run_sync() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"], ctx.obj["filename"])
        mgr = UserManager(connect)
        try:
            await mgr.db_sync()
        except MQTTError as me:
            logger.critical("Could not sync schema on db.")
            raise typer.Exit(code=1) from me

    asyncio.run(run_sync())


@user_app.command(name="list")
def list_clients(ctx: typer.Context) -> None:
    """List all Client IDs (in alphabetical order). Will also display the hashed passwords."""

    async def run_list() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"], ctx.obj["filename"])
        mgr = UserManager(connect)
        user_count = 0
        for user in await mgr.list_users():
            user_count += 1
            logger.info(user)

        if not user_count:
            logger.info("No users exist.")

    asyncio.run(run_list())


@user_app.command(name="add")
def create_client(
        ctx: typer.Context,
        client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the new client")],
        ) -> None:
    """Create a new user with a client id and password (prompted)."""
    async def run_create() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = UserManager(connect)
        client_password = Prompt.ask("Enter the client password", password=True)
        if not client_password:
            logger.error("Client password cannot be empty.")
            raise typer.Exit(1)
        try:
            user = await mgr.create_user(client_id, client_password)
        except passlib.exc.MissingBackendError as mbe:
            logger.critical(f"Please install backend: {mbe}")
            raise typer.Exit(code=1) from mbe

        if not user:
            logger.error(f"Could not create user: {client_id}")
            raise typer.Exit(code=1)

        logger.info(f"User created: {user}")

    asyncio.run(run_create())


@user_app.command(name="rm")
def remove_username(ctx: typer.Context,
                    client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the client to remove")]) -> None:
    """Remove a client from the authentication database."""
    async def run_remove() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = UserManager(connect)
        user = await mgr.delete_user(client_id)
        if not user:
            logger.error(f"User '{client_id}' not found.")
            raise typer.Exit(1)
        logger.info(f"'{user.username}' was removed.")

    if not Confirm.ask(f"Please confirm the removal of '{client_id}'?"):
        raise typer.Exit(1)

    asyncio.run(run_remove())


@user_app.command(name="pwd")
def change_password(
        ctx: typer.Context,
        client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the new client")],
        ) -> None:
    """Update a user's password (prompted)."""
    async def run_password() -> None:
        client_password = Prompt.ask("Enter the client's new password", password=True)
        if not client_password:
            logger.error("Client password cannot be empty.")
            raise typer.Exit(1)
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = UserManager(connect)
        await mgr.update_password(client_id, client_password)

    asyncio.run(run_password())


if __name__ == "__main__":
    user_app()
