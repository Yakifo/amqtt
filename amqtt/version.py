try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc

import logging
from pathlib import Path
import shutil
import subprocess
import warnings

import amqtt

logger = logging.getLogger(__name__)


def get_version() -> str:
    """Return the version of the amqtt package.

    This function is deprecated. Use amqtt.__version__ instead.
    """
    warnings.warn(
        "amqtt.version.get_version() is deprecated, use amqtt.__version__ instead",
        stacklevel=3,  # Adjusted stack level to better reflect the caller
    )
    return amqtt.__version__


def get_git_changeset() -> str | None:
    """Return a numeric identifier of the latest git changeset.

    The result is the UTC timestamp of the changeset in YYYYMMDDHHMMSS format.
    This value isn't guaranteed to be unique, but collisions are very unlikely,
    so it's sufficient for generating the development version numbers.
    """
    # Define the repository directory (two levels above the current script)
    repo_dir = Path(__file__).resolve().parent.parent

    # Ensure the directory exists and is valid
    if not repo_dir.is_dir():
        logger.error(f"Invalid directory: {repo_dir} is not a valid directory")
        return None

    # Use the system's PATH to locate 'git', or define the full path if necessary
    git_path = "git"  # Assuming git is available in the system PATH

    # Ensure 'git' is executable and available
    if not shutil.which(git_path):
        logger.error(f"{git_path} is not found in the system PATH.")
        return None

    # Call git log to get the latest changeset timestamp
    try:
        with subprocess.Popen(  # noqa: S603
            [git_path, "log", "--pretty=format:%ct", "--quiet", "-1", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=repo_dir,
            universal_newlines=True,
        ) as git_log:
            timestamp_str, stderr = git_log.communicate()

            if git_log.returncode != 0:
                logger.error(f"Git command failed with error: {stderr}")
                return None

            # Convert the timestamp to a datetime object
            timestamp = datetime.fromtimestamp(int(timestamp_str), tz=UTC)
            return timestamp.strftime("%Y%m%d%H%M%S")

    except Exception:
        logger.exception("An error occurred while retrieving the git changeset.")
    return None
