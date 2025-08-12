# Authentication with LDAP Server

If clients accessing the broker are managed by an LDAP server, this plugin can verify credentials
for client authentication and/or topic-level authorization.

- `amqtt.contrib.ldap.UserAuthLdapPlugin` (client authentication)
- `amqtt.contrib.ldap.TopicAuthLdapPlugin` (topic authorization)

Authenticate a user with an LDAP directory server.

# User Auth

::: amqtt.contrib.ldap.UserAuthLdapPlugin.Config
    options:
      heading_level: 4
      extra:
        class_style: "simple"

# Topic Auth (ACL)

::: amqtt.contrib.ldap.TopicAuthLdapPlugin.Config
    options:
      heading_level: 4
      extra:
        class_style: "simple"
