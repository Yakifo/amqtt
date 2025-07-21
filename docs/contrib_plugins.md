# Contributed Plugins

Plugins that are not part of the core functionality of the aMQTT broker or client, often requiring additional dependencies.


## Authentication from relational database

`amqtt.contrib.auth_db.AuthDBPlugin`

Using SQLAlchemy to support MySQL, MariaDB, Postgres and SQLite, this plugin supports authenticating clients against
a relational database. In its default state, it uses its own schema to track clients and their credentials.

For ease of use, there is a [command-line utility](contrib_plugins.md/#auth_db) to add, remove, update and list clients. 

::: amqtt.contrib.auth_db.plugin.AuthDBPlugin.Config

## Command line utility for auth via database

::: mkdocs-typer2
    :module: amqtt.contrib.auth_db.cli
    :name: auth_db