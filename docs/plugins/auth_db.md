# Relational Database for Authentication and Authorization

- `amqtt.contrib.auth_db.UserAuthDBPlugin` (authentication) verify a client's ability to connect to broker
- `amqtt.contrib.auth_db.TopicAuthDBPlugin` (authorization) determine a client's access to topics

Relational database access is supported using SQLAlchemy so MySQL, MariaDB, Postgres and SQLite support is available.

For ease of use, the [`user_mgr` command-line utility](auth_db.md/#user_mgr) to add, remove, update and 
list clients. And the [`topic_mgr` command-line utility](auth_db.md/#topic_mgr) to add client access to
subscribe, publish and receive messages on topics.

# Authentication Configuration

::: amqtt.contrib.auth_db.UserAuthDBPlugin.Config
    options:
      heading_level: 4
      extra:
        class_style: "simple"

# Authorization Configuration

::: amqtt.contrib.auth_db.TopicAuthDBPlugin.Config
    options:
      heading_level: 4
      extra:
        class_style: "simple"

## CLI


::: mkdocs-typer2
    :module: amqtt.contrib.auth_db.user_mgr_cli
    :name: user_mgr


::: mkdocs-typer2
    :module: amqtt.contrib.auth_db.topic_mgr_cli
    :name: topic_mgr

