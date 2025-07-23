import logging
import sys

from amqtt.errors import MQTTError

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the auth db cli."""
    try:
        from amqtt.contrib.auth_db.user_mgr_cli import user_app  #  pylint: disable=import-outside-toplevel
    except ImportError:
        logger.critical("optional 'contrib' library is missing, please install: `pip install amqtt[contrib]`")
        sys.exit(1)

    from amqtt.contrib.auth_db.user_mgr_cli import user_app  #  pylint: disable=import-outside-toplevel
    try:
        user_app()
    except ModuleNotFoundError as mnfe:
        logger.critical(f"Please install database-specific dependencies: {mnfe}")
        sys.exit(1)
    except ValueError as ve:
        if "greenlet" in f"{ve}":
            logger.critical("Please install database-specific dependencies: 'greenlet'")
            sys.exit(1)
        logger.critical(f"Unknown error: {ve}")
        sys.exit(1)

    except MQTTError as me:
        logger.critical(f"could not execute command: {me}")
        sys.exit(1)

if __name__ == "__main__":
    main()
