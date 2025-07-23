# Contributed Plugins

Plugins that are not part of the core functionality of the aMQTT broker or client, often requiring additional dependencies.


## Relational Database for Authentication and Authorization

- `amqtt.contrib.auth_db.AuthUserDBPlugin` (authentication) verify a client's ability to connect to broker
- `amqtt.contrib.auth_db.AuthTopicDBPlugine` (authorization) determine a client's access to topics  

Relational database access is supported using SQLAlchemy so MySQL, MariaDB, Postgres and SQLite support is available.

For ease of use, the [`user_mgr` command-line utility](contrib_plugins.md/#user_mgr) to add, remove, update and 
list clients. And the [`topic_mgr` command-line utility](contrib_plugins.md/#user_topic) to add client access to
subscribe, publish and receive messages on topics.

## Authentication Configuration

::: amqtt.contrib.auth_db.UserAuthDBPlugin.Config

## Authorization Configuration

::: amqtt.contrib.auth_db.TopicAuthDBPlugin.Config

## Command line for authentication

::: mkdocs-typer2
    :module: amqtt.contrib.auth_db.user_mgr_cli
    :name: user_mgr

## Command line for authorization

::: mkdocs-typer2
    :module: amqtt.contrib.auth_db.topic_mgr_cli
    :name: topic_mgr
