import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated
import typer
from amqtt.contrib.auth_db.plugin import UserManager
from amqtt.errors import MQTTError
# from enum import StrEnum

from rich.prompt import Prompt, Confirm
import passlib


logger = logging.getLogger(__name__)
app = typer.Typer(no_args_is_help=True)


class DBType(StrEnum):
    MARIA = "mariadb"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


@dataclass
class DBInfo:
    connect_str: str
    connect_port: int | None


_db_map = {
    DBType.MARIA: DBInfo('mysql+aiomysql', 3306),
    DBType.MYSQL: DBInfo('mysql+aiomysql', 3306),
    DBType.POSTGRESQL: DBInfo('postgresql+asyncpg', 5432),
    DBType.SQLITE: DBInfo('sqlite+aiosqlite', None)
}


@dataclass(kw_only=True)
class CommonArgs:
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output.")] = False
    config_path: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file.")] = "config.ini"


def db_connection_str(db_type: DBType, db_username: str, db_host:str, db_port: int|None, db_filename: str) -> str:
    db_info = _db_map[db_type]
    if db_type == DBType.SQLITE:
        return f"{db_info.connect_str}:///{db_filename}"
    db_password = Prompt.ask("Enter the db password (press enter for none)", password=True)
    pwd = f':{db_password}' if db_password else ''
    return f"{db_info.connect_str}://{db_username}:{pwd}@{db_host}:{db_port or db_info.connect_port}"


@app.callback()
def main(
        ctx: typer.Context,
        db_type: Annotated[DBType, typer.Option("--db", "-d", help="db type", count=False)],
        db_username: Annotated[str, typer.Option("--username", "-u", help="db username")] = None,
        db_port: Annotated[int, typer.Option("--port", "-p", help="database port (defaults to db type)")] = None,
        db_host: Annotated[str, typer.Option("--host", "-h", help="database host")] = "localhost",
        db_filename: Annotated[str, typer.Option("--file", "-f", help="database file name (sqlite only)")] = "auth.db",
        verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output.")] = False,

):
    if db_type == DBType.SQLITE and ctx.invoked_subcommand == "sync" and not Path(db_filename).exists():
        pass
    elif db_type == DBType.SQLITE and not Path(db_filename).exists():
        logger.error(f"SQLite option could not find '{db_filename}'")
        raise typer.Exit()
    elif db_type != DBType.SQLITE and not db_username:
        logger.error("DB access requires a username be provided.")
        raise typer.Exit()

    ctx.obj = {'type': db_type, 'username': db_username, 'host': db_host, 'port': db_port, 'filename': db_filename}


@app.command(name='sync')
def db_sync(ctx: typer.Context):
    async def run_sync():
        connect = db_connection_str(ctx.obj['type'], ctx.obj['username'], ctx.obj['host'], ctx.obj['port'], ctx.obj['filename'])
        mgr = UserManager(connect)
        try:
            await mgr.db_sync()
        except MQTTError:
            logger.error("Could not sync schema on db.")
            raise typer.Exit()

    asyncio.run(run_sync())


@app.command(name="list")
def list_clients(ctx: typer.Context) -> None:
    """List all Client IDs."""
    async def run_list() -> None:
        connect = db_connection_str(ctx.obj['type'], ctx.obj['username'], ctx.obj['host'], ctx.obj['port'], ctx.obj['filename'])
        mgr = UserManager(connect)
        user_count = 0
        for user in await mgr.list_users():
            user_count += 1
            print(user)

        if not user_count:
            print("No users exist.")

    asyncio.run(run_list())



@app.command(name="add")
def create_client(
        ctx: typer.Context,
        client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the new client")],
        ) -> None:
    """create a username"""
    async def run_create() -> None:
        connect = db_connection_str(ctx.obj['type'], ctx.obj['username'], ctx.obj['host'], ctx.obj['port'],
                                    ctx.obj['filename'])
        mgr = UserManager(connect)
        client_password = Prompt.ask("Enter the client password", password=True)
        if not client_password:
            logger.error("Client password cannot be empty.")
            raise typer.Exit()
        try:
            user = await mgr.create_user(client_id, client_password)
        except passlib.exc.MissingBackendError as mbe:
            logger.error(f"Please install backend: {mbe}")
            raise typer.Exit()

        if not user:
            logger.error(f"Could not create user: {client_id}")
            raise typer.Exit()

        print(f"User created: {user}")

    asyncio.run(run_create())



@app.command(name="rm")
def remove_username(ctx: typer.Context,
                    client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the client to remove")]) -> None:
    """remove a username"""
    async def run_remove() -> None:
        connect = db_connection_str(ctx.obj['type'], ctx.obj['username'], ctx.obj['host'], ctx.obj['port'],
                                    ctx.obj['filename'])
        mgr = UserManager(connect)
        user = await mgr.delete_user(client_id)
        print(f"'{user.username}' was removed.")

    if not Confirm.ask(f"Please confirm the removal of '{client_id}'?"):
        raise typer.Exit()

    asyncio.run(run_remove())



@app.command(name="pwd")
def change_password(
        ctx: typer.Context,
        client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the new client")],
        ) -> None:
    """update a user's password"""
    async def run_password() -> None:
        client_password = Prompt.ask("Enter the client's new password", password=True)
        if not client_password:
            logger.error("Client password cannot be empty.")
            raise typer.Exit()
        connect = db_connection_str(ctx.obj['type'], ctx.obj['username'], ctx.obj['host'], ctx.obj['port'],
                                    ctx.obj['filename'])
        mgr = UserManager(connect)
        await mgr.update_password(client_id, client_password)

    asyncio.run(run_password())

