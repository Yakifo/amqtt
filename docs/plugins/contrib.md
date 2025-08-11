# Contributed Plugins

These are fully supported plugins but require additional dependencies to be installed: 

`$ pip install '.[contrib]'`


- [Relational Database Auth](auth_db.md)<br/>
  Grant or deny access to clients based on entries in a relational db (mysql, postgres, maria, sqlite). _Includes
   manager script to add, remove and create db entries_<br/>
    - `amqtt.contrib.auth_db.UserAuthDBPlugin`
    - `amqtt.contrib.auth_db.TopicAuthDBPlugin`

- [HTTP Auth](http.md)<br/>
  Determine client authentication and/or authorization based on response from a separate HTTP server.<br/>
    - `amqtt.contrib.http.UserAuthHttpPlugin`
    - `amqtt.contrib.http.TopicAuthHttpPlugin`

- [LDAP Auth](ldap.md)<br/>
  Authenticate a user with an LDAP directory server.<br/>
    - `amqtt.contrib.ldap.UserAuthLdapPlugin`
    - `amqtt.contrib.ldap.TopicAuthLdapPlugin`

- [Shadows](shadows.md)<br/>
  Device shadows provide a persistent, cloud-based representation of the state of a device,
   even when the device is offline. This plugin tracks the desired and reported state of a client
   and provides MQTT topic-based communication channels to retrieve and update a shadow.<br/>
   `amqtt.contrib.shadows.ShadowPlugin`

- [Certificate Auth](cert.md)<br/>
  Using client-specific certificates, signed by a common authority (even if self-signed) provides
   a highly secure way of authenticating mqtt clients. Often used with IoT devices where a unique
   certificate can be initialized on initial provisioning. _Includes command line utilities to generate
   root, broker and device certificates with the correct X509
   attributes to enable authenticity._<br/>
   `amqtt.contrib.cert.UserAuthCertPlugin`

- [JWT Auth](jwt.md)<br/>
  Plugin to determine user authentication and topic authorization based on claims in a JWT.
    - `amqtt.contrib.jwt.UserAuthJwtPlugin` (client authentication)
    - `amqtt.contrib.jwt.TopicAuthJwtPlugin` (topic authorization) 

- [Session Persistence](session.md)<br/>
  Plugin to store session information and retained topic messages in the event that the broker terminates abnormally.<br/>
  `amqtt.contrib.persistence.SessionDBPlugin`
