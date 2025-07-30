import asyncio
import logging
from pathlib import Path
from typing import Annotated

import click
import passlib
import typer

from amqtt.contrib.auth_db import DBType, db_connection_str
from amqtt.contrib.auth_db.managers import UserManager
from amqtt.errors import MQTTError

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
user_app = typer.Typer(no_args_is_help=True)


@user_app.callback()
def main(
        ctx: typer.Context,
        db_type: Annotated[DBType, typer.Option(..., "--db", "-d", help="db type", show_default=False)],
        db_username: Annotated[str, typer.Option("--username", "-u", help="db username", show_default=False)] = "",
        db_port: Annotated[int, typer.Option("--port", "-p", help="database port (defaults to db type)", show_default=False)] = 0,
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
    logger.info("Success: database synced.")


@user_app.command(name="list")
def list_user_auths(ctx: typer.Context) -> None:
    """List all Client IDs (in alphabetical order). Will also display the hashed passwords."""

    async def run_list() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"], ctx.obj["filename"])
        mgr = UserManager(connect)
        user_count = 0
        for user in await mgr.list_user_auths():
            user_count += 1
            logger.info(user)

        if not user_count:
            logger.info("No client authentications exist.")

    asyncio.run(run_list())


@user_app.command(name="add")
def create_user_auth(
        ctx: typer.Context,
        client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the new client")],
        ) -> None:
    """Create a new user with a client id and password (prompted)."""
    async def run_create() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = UserManager(connect)
        client_password = click.prompt("Enter the client's password", hide_input=True)
        if not client_password.strip():
            logger.info("Error: client password cannot be empty.")
            raise typer.Exit(1)
        try:
            user = await mgr.create_user_auth(client_id, client_password.strip())
        except passlib.exc.MissingBackendError as mbe:
            logger.info(f"Please install backend: {mbe}")
            raise typer.Exit(code=1) from mbe

        if not user:
            logger.info(f"Error: could not create user: {client_id}")
            raise typer.Exit(code=1)

        logger.info(f"Success: created {user}")

    asyncio.run(run_create())


@user_app.command(name="rm")
def remove_user_auth(ctx: typer.Context,
                     client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the client to remove")]) -> None:
    """Remove a client from the authentication database."""
    async def run_remove() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = UserManager(connect)
        user = await mgr.get_user_auth(client_id)
        if not user:
            logger.info(f"Error: client '{client_id}' does not exist.")
            raise typer.Exit(1)

        if not click.confirm(f"Please confirm the removal of '{client_id}'?"):
            raise typer.Exit(0)

        user = await mgr.delete_user_auth(client_id)
        if not user:
            logger.info(f"Error: client '{client_id}' does not exist.")
            raise typer.Exit(1)

        logger.info(f"Success: '{user.username}' was removed.")

    asyncio.run(run_remove())


@user_app.command(name="pwd")
def change_password(
        ctx: typer.Context,
        client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the new client")],
        ) -> None:
    """Update a user's password (prompted)."""
    async def run_password() -> None:
        client_password = click.prompt("Enter the client's new password", hide_input=True)
        if not client_password.strip():
            logger.error("Error: client password cannot be empty.")
            raise typer.Exit(1)
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = UserManager(connect)
        await mgr.update_user_auth_password(client_id, client_password.strip())
        logger.info(f"Success: client '{client_id}' password updated.")

    asyncio.run(run_password())


if __name__ == "__main__":
    user_app()
