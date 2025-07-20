import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the auth db cli."""
    try:
        from amqtt.contrib.auth_db.cli import auth_app
        auth_app()
    except ImportError:
        print("optional 'contrib' library is missing, please install: `pip install amqtt[contrib]`")



if __name__ == "__main__":
    main()
