# Contributed Plugins

These are fully supported plugins but require additional dependencies to be installed: 

`$ pip install '.[contrib]'`


- Relational Database Auth<br/>
  _includes manager script to add, remove and create db entries_
    - [DB Client Authentication](auth_db.md)<br/>
      Authenticate a client's connection to broker based on entries in a relational db (mysql, postgres, maria, sqlite).<br/>
      `amqtt.contrib.auth_db.AuthUserDBPlugin`
    - [DB Client Authorization](auth_db.md)<br/>
      Determine a client's access to topics.<br/>
      `amqtt.contrib.auth_db.AuthTopicDBPlugin`

- [HTTP Auth](http.md)<br/>
  Determine client authentication and authorization based on response from a separate HTTP server.<br/>
  `amqtt.contrib.http.HttpAuthTopicPlugin`

- [LDAP Auth](ldap.md)<br/>
  Authenticate a user with an LDAP directory server.<br/>
  `amqtt.contrib.ldap.LDAPAuthPlugin`