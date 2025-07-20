#
# import logging
# from dataclasses import dataclass
# from enum import StrEnum
#
# from typing import Annotated
# from rich.prompt import Prompt
#
#
# import typer
# import typer_di
# import click
#
#
# logger = logging.getLogger(__name__)
#
#
# app = typer_di.TyperDI(add_completion=False, rich_markup_mode=None)
#
#
from enum import StrEnum


class DBType(StrEnum):
    MARIA = "mariadb"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"

#
# @dataclass
# class DBInfo:
#     connect_str: str
#     connect_port: int | None
#
#
# _db_map = {
#     DBType.MARIA: DBInfo('mysql+aiomysql', 8888),
#     DBType.MYSQL: DBInfo('mysql+aiomysql', 8888),
#     DBType.POSTGRESQL: DBInfo('postgresql+asyncpg', 8888),
#     DBType.SQLITE: DBInfo('sqlite+aiosqlite', None)
# }
#
# required_options = {
#     DBType.MARIA: 'host,username',
#     DBType.SQLITE: 'filename'
# }
#
#
#
#
# def command_required_option_from_option(require_name, require_map):
#
#     class CommandOptionRequiredClass(click.Command):
#
#         def invoke(self, ctx):
#             require = ctx.params[require_name]
#             if require not in require_map:
#                 raise click.ClickException(
#                     "Unexpected value for --'{}': {}".format(
#                         require_name, require))
#             if ctx.params[require_map[require].lower()] is None:
#                 raise click.ClickException(
#                     "With {}={} must specify option --{}".format(
#                         require_name, require, require_map[require]))
#             super(CommandOptionRequiredClass, self).invoke(ctx)
#
# # @dataclass(kw_only=True)
# # class CommonArgs:
# #     db_type: Annotated[DBType, typer.Option("--db", "-d", help="db type")]
# #     db_username: Annotated[str, typer.Option("--username", "-u", help="set the username", prompt="Enter db username")]
# #     db_host: Annotated[str, typer.Option("--host", "-h", help="database host", prompt="Enter db username")] = "localhost"
# #     verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output.")] = False
# #     config_path: Annotated[str, typer.Option("--config", "-c", help="Path to configuration file.")] = "config.ini"
# #
#
#
#
# @app.command(name="list")
# def list_clients(db_type: Annotated[DBType, typer.Option("--db", "-d", help="db type")]):
#     """List all Client IDs."""
#
#
# @app.command(name="add")
# def create_username(debug: bool = typer.Option(False, "-d", help="Enable debug messages")):
#     """create a username"""
#     password = Prompt.ask("Enter the db password", password=True)
#
# @app.command(name="rm")
# def remove_usernames(debug: bool = typer.Option(False, "-d", help="Enable debug messages")):
#     """remove a username"""
#     password = Prompt.ask("Enter the db password", password=True)
#
# @app.command(name="pwd")
# def change_password(debug: bool = typer.Option(False, "-d", help="Enable debug messages")):
#     """update a user's password"""
#     password = Prompt.ask("Enter the db password", password=True)

import click
import typer

_app = typer.Typer()


@_app.command()
def top():
    """
    Top level command, form Typer
    """
    print("The Typer app is at the top level")


@_app.callback()
def callback():
    """
    Typer app, including Click subapp
    """


def command_required_option_from_option(require_name, require_map):

    class CommandOptionRequiredClass(click.Command):

        def invoke(self, ctx):
            require = ctx.params[require_name]
            if require not in require_map:
                raise click.ClickException(
                    "Unexpected value for --'{}': {}".format(
                        require_name, require))
            if ctx.params[require_map[require].lower()] is None:
                raise click.ClickException(
                    "With {}={} must specify option --{}".format(
                        require_name, require, require_map[require]))
            super(CommandOptionRequiredClass, self).invoke(ctx)

    return CommandOptionRequiredClass


required_options = {
    1: 'generator_string',
    2: 'number_of_sample_points',
    3: 'number_of_center_points',
}


@click.command(context_settings=dict(max_content_width=800),
               cls=command_required_option_from_option('doe', required_options))
@click.option('--input', required=True,
              type=click.Path(exists=True))
@click.option('--doe', required=True, type=int)
@click.option('--generator_string', required=False, type=str, is_eager=True)
@click.option('--number_of_sample_points', required=False, type=int, is_eager=True)
@click.option('--number_of_center_points', required=False, type=int, is_eager=True)
def hello(name):
    """Simple program that greets NAME for a total of COUNT times."""
    click.echo(f"Hello {name}!")


from amqtt.scripts.constrained_option import ConstrainedOption


@click.command()
@click.option(cls=ConstrainedOption,
              group_require_one=["apple", "orange", "pear"])
@click.option("--apple",
              cls=ConstrainedOption,
              is_flag=True)
@click.option("--orange",
              cls=ConstrainedOption,
              is_flag=True)
@click.option("--pear",
              cls=ConstrainedOption,
              is_flag=True)
def cli(**kwargs):
    click.echo(kwargs)



def my_command_function(count, name):
    for _ in range(count):
        click.echo(f"Hello {name}!")

my_command = click.command(name="cmd")(my_command_function)

count_option = click.Option(
    ["--db", "-d"],
    default=1,
    type=click.Choice(DBType),
    help="type of database",
)
my_command.params.append(count_option)

name_option = click.Option(
    ["--name", "-n"],
    prompt="Your name",
    help="The person to greet.",
)
my_command.params.append(name_option)


import cloup
from cloup.constraints import (
    If, require_one, Equal
)

@cloup.command(show_constraints=True)
@click.option('-f', '--format', required=True,
              type=click.Choice(['csv', 'json']))
@click.option('-d', '--delimiter', required=False, type=click.Choice(['\t', ', ']))
@click.option('-i', '--indent', required=False, type=int)
@cloup.constraint(If(Equal('format', 'csv'), then=require_one.hidden()), ['delimiter'])
@cloup.constraint(If(Equal('format', 'json'), then=require_one.hidden()), ['indent'])
def formatter(format, delimiter, indent):
    pass







auth_app = typer.main.get_command(_app)

auth_app.add_command(hello, "hello")
auth_app.add_command(cli, "cli")
auth_app.add_command(my_command, "cmd")
auth_app.add_command(formatter, "formatter")









# if __name__ == "__main__":
#     typer_click_object()

