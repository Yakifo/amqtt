from dataclasses import dataclass
import logging
from typing import ClassVar

import ldap

from amqtt.broker import BrokerContext
from amqtt.contexts import Action
from amqtt.errors import PluginInitError
from amqtt.plugins import TopicMatcher
from amqtt.plugins.base import BaseAuthPlugin, BasePlugin, BaseTopicPlugin
from amqtt.session import Session

logger = logging.getLogger(__name__)


@dataclass
class LdapConfig:
    """Configuration for the LDAP Plugins."""

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


class AuthLdapPlugin(BasePlugin[BrokerContext]):

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        self.conn = ldap.initialize(self.config.server)
        self.conn.protocol_version = ldap.VERSION3  # pylint: disable=E1101
        try:
            self.conn.simple_bind_s(self.config.bind_dn, self.config.bind_password)
        except ldap.INVALID_CREDENTIALS as e:  # pylint: disable=E1101
            raise PluginInitError(self.__class__) from e


class UserAuthLdapPlugin(AuthLdapPlugin, BaseAuthPlugin):
    """Plugin to authenticate a user with an LDAP directory server."""

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
    class Config(LdapConfig):
        """Configuration for the User Auth LDAP Plugin."""


class TopicAuthLdapPlugin(AuthLdapPlugin, BaseTopicPlugin):
    """Plugin to authenticate a user with an LDAP directory server."""

    _action_attr_map: ClassVar = {
        Action.PUBLISH: "publish_attribute",
        Action.SUBSCRIBE: "subscribe_attribute",
        Action.RECEIVE: "receive_attribute"
    }

    def __init__(self, context: BrokerContext) -> None:
        super().__init__(context)

        self.topic_matcher = TopicMatcher()

    async def topic_filtering(
        self, *, session: Session | None = None, topic: str | None = None, action: Action | None = None
    ) -> bool | None:

        # if not provided needed criteria, can't properly evaluate topic filtering
        if not session or not action or not topic:
            return None

        search_filter = f"({self.config.user_attribute}={session.username})"
        attrs = [
            "cn",
            self.config.publish_attribute,
            self.config.subscribe_attribute,
            self.config.receive_attribute
        ]
        results = self.conn.search_s(self.config.base_dn, ldap.SCOPE_SUBTREE, search_filter, attrs)  # pylint: disable=E1101

        if not results:
            logger.debug(f"user not found: {session.username}")
            return False

        if len(results) > 1:
            found_users = [dn for dn, _ in results]
            logger.debug(f"multiple users found: {', '.join(found_users)}")
            return False

        dn, entry = results[0]

        ldap_attribute = getattr(self.config, self._action_attr_map[action])
        topic_filters = [t.decode("utf-8") for t in entry.get(ldap_attribute, [])]
        logger.debug(f"DN: {dn} - {ldap_attribute}={topic_filters}")

        return self.topic_matcher.are_topics_allowed(topic, topic_filters)

    @dataclass
    class Config(LdapConfig):
        """Configuration for the LDAPAuthPlugin."""

        publish_attribute: str
        """LDAP attribute which contains a list of permissible publish topics."""
        subscribe_attribute: str
        """LDAP attribute which contains a list of permissible subscribe topics."""
        receive_attribute: str
        """LDAP attribute which contains a list of permissible receive topics."""
