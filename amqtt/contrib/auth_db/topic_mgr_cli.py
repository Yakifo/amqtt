import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Annotated

import typer

from amqtt.contexts import Action
from amqtt.contrib.auth_db import DBType, db_connection_str
from amqtt.contrib.auth_db.managers import TopicManager, UserManager
from amqtt.errors import MQTTError

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
topic_app = typer.Typer(no_args_is_help=True)


@topic_app.callback()
def main(
        ctx: typer.Context,
        db_type: Annotated[DBType, typer.Option("--db", "-d", help="db type", count=False)],
        db_username: Annotated[str, typer.Option("--username", "-u", help="db username", show_default=False)] = "",
        db_port: Annotated[int, typer.Option("--port", "-p", help="database port (defaults to db type)", show_default=False)] = 0,
        db_host: Annotated[str, typer.Option("--host", "-h", help="database host")] = "localhost",
        db_filename: Annotated[str, typer.Option("--file", "-f", help="database file name (sqlite only)")] = "auth.db",
) -> None:
    """Command line interface to add / remove topic authorization.

    Passwords are not allowed to be passed via the command line for security reasons. You will be prompted for database
    password (if applicable).

    If you need to create users programmatically, see `amqtt.contrib.auth_db.managers.TopicManager` which provides
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


@topic_app.command(name="sync")
def db_sync(ctx: typer.Context) -> None:
    """Create the table and schema for username and topic lists for subscribe, publish or receive.

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


@topic_app.command(name="list")
def list_clients(ctx: typer.Context) -> None:
    """List all Client IDs (in alphabetical order). Will also display the hashed passwords."""

    async def run_list() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"], ctx.obj["filename"])
        mgr = TopicManager(connect)
        user_count = 0
        for user in await mgr.list_topic_auths():
            user_count += 1
            logger.info(user)

        if not user_count:
            logger.info("No client authorizations exist.")

    asyncio.run(run_list())


@topic_app.command(name="add")
def add_topic_allowance(
        ctx: typer.Context,
        topic: Annotated[str, typer.Argument(help="list of topics", show_default=False)],
        client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the client", show_default=False)],
        action: Annotated[Action, typer.Option("--action", "-a", help="action for topic to allow", show_default=False)]
        ) -> None:
    """Create a new user with a client id and password (prompted)."""
    async def run_add() -> None:

        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = TopicManager(connect)

        with contextlib.suppress(MQTTError):
            await mgr.create_topic_auth(client_id)

        topic_auth = await mgr.get_topic_auth(client_id)
        if not topic_auth:
            logger.info(f"Topic auth doesn't exist for '{client_id}'")
            raise typer.Exit(code=1)

        if topic in [allowed_topic.topic for allowed_topic in topic_auth.get_topic_list(action)]:
            logger.info(f"Topic '{topic}' already exists for '{action}'.")
            raise typer.Exit(1)

        await mgr.add_allowed_topic(client_id, topic, action)

        logger.info(f"Success: topic '{topic}' added to {action} for '{client_id}'")

    asyncio.run(run_add())


@topic_app.command(name="rm")
def remove_topic_allowance(ctx: typer.Context,
                           client_id: Annotated[str, typer.Option("--client-id", "-c", help="id for the client to remove")],
                           action: Annotated[Action, typer.Option("--action", "-a", help="action for topic to allow")],
                           topic: Annotated[str, typer.Argument(help="list of topics")]
                           ) -> None:
    """Remove a client from the authentication database."""
    async def run_remove() -> None:
        connect = db_connection_str(ctx.obj["type"], ctx.obj["username"], ctx.obj["host"], ctx.obj["port"],
                                    ctx.obj["filename"])
        mgr = TopicManager(connect)

        topic_auth = await mgr.get_topic_auth(client_id)

        if not topic_auth:
            logger.info(f"client '{client_id}' doesn't exist.")
            raise typer.Exit(1)

        if topic not in getattr(topic_auth, f"{action}_acl"):
            logger.info(f"Error: topic '{topic}' not in the {action} allow list for {client_id}.")
            raise typer.Exit(1)

        try:
            await mgr.remove_allowed_topic(client_id, topic, action)
        except MQTTError as me:
            logger.info(f"'Error: could not remove '{topic}' for client '{client_id}'.")
            raise typer.Exit(1) from me

        logger.info(f"Success: removed topic '{topic}' from {action} for '{client_id}'")

    asyncio.run(run_remove())


if __name__ == "__main__":
    topic_app()
