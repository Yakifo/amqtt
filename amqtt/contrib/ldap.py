from dataclasses import dataclass
import logging

import ldap

from amqtt.broker import BrokerContext
from amqtt.errors import PluginInitError
from amqtt.plugins.base import BaseAuthPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


class LDAPAuthPlugin(BaseAuthPlugin):
    """Plugin to authenticate a user with an LDAP directory server."""

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        self.conn = ldap.initialize(self.config.server)
        self.conn.protocol_version = ldap.VERSION3  # pylint: disable=E1101
        try:
            self.conn.simple_bind_s(self.config.bind_dn, self.config.bind_password)
        except ldap.INVALID_CREDENTIALS as e:  # pylint: disable=E1101
            raise PluginInitError(self.__class__) from e


    async def authenticate(self, *, session: Session) -> bool | None:

        # use our initial creds to see if the user exists
        search_filter = f"({self.config.user_attribute}={session.username})"
        result = self.conn.search_s(self.config.base_dn, ldap.SCOPE_SUBTREE, search_filter, ["dn"])  # pylint: disable=E1101
        if not result:
            logger.debug(f"user not found: {session.username}")
            return False

        try:
            # `search_s` responds with list of tuples: (dn, entry); first in list is our match
            user_dn = result[0][0]
        except IndexError:
            return False

        try:
            user_conn = ldap.initialize(self.config.server)
            user_conn.simple_bind_s(user_dn, session.password)
        except ldap.INVALID_CREDENTIALS:  # pylint: disable=E1101
            logger.debug(f"invalid credentials for '{session.username}'")
            return False
        except ldap.LDAPError as e:  # pylint: disable=E1101
            logger.debug(f"LDAP error during user bind: {e}")
            return False

        return True

    @dataclass
    class Config:
        """Configuration for the LDAPAuthPlugin."""

        server: str
        """uri formatted server location. e.g `ldap://localhost:389`"""
        base_dn: str
        """distinguished name (dn) of the ldap server. e.g. `dc=amqtt,dc=io`"""
        user_attribute: str
        """attribute in ldap entry to match the username against"""
        bind_dn: str
        """distinguished name (dn) of known, preferably read-only, user. e.g. `cn=admin,dc=amqtt,dc=io`"""
        bind_password: str
        """password for known, preferably read-only, user"""
