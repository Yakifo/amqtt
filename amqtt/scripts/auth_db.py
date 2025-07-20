import logging
import sys

from amqtt.errors import MQTTError

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the auth db cli."""
    try:
        from amqtt.contrib.auth_db.cli import app
    except ImportError as ie:
        print("optional 'contrib' library is missing, please install: `pip install amqtt[contrib]`")
        sys.exit(1)

    from amqtt.contrib.auth_db.cli import app
    try:
        app()
    except ModuleNotFoundError as mnfe:
        print(f"Please install database-specific dependencies: {mnfe}")
        sys.exit(1)
    except ValueError as ve:
        if 'greenlet' in f"{ve}":
            print(f"Please install database-specific dependencies: 'greenlet'")
            sys.exit(1)
        print(f"Unknown error: {ve}")
        sys.exit(1)

    except MQTTError as me:
        print(f"could not execute command: {me}")




if __name__ == "__main__":
    main()
