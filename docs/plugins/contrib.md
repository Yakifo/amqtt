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

- [Shadows](shadows.md)<br/>
  Device shadows provide a persistent, cloud-based representation of the state of a device,
   even when the device is offline. This plugin tracks the desired and reported state of a client
   and provides MQTT topic-based communication channels to retrieve and update a shadow.<br/>
   `amqtt.contrib.shadows.ShadowPlugin`

- [Certificate Auth](cert.md)<br/>
  Using client-specific certificates, signed by a common authority (even if self-signed) provides
   a highly secure way of authenticating mqtt clients. Often used with IoT devices where a unique
   certificate can be initialized on initial provisioning. Includes command line utilities to generate
   root, broker and device certificates with the correct X509 attributes to enable authenticity.<br/>
   `amqtt.contrib.cert.CertificateAuthPlugin.Config`
