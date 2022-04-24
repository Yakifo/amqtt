# See the file license.txt for copying permission.
import datetime
import os
import subprocess
import warnings
from typing import Optional

import amqtt


def get_version() -> str:
    warnings.warn(
        "amqtt.version.get_version() is deprecated, use amqtt.__version__ instead"
    )
    return amqtt.__version__


def get_git_changeset() -> Optional[str]:
    """Returns a numeric identifier of the latest git changeset.
    The result is the UTC timestamp of the changeset in YYYYMMDDHHMMSS format.
    This value isn't guaranteed to be unique, but collisions are very unlikely,
    so it's sufficient for generating the development version numbers.
    """
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_log = subprocess.Popen(
        "git log --pretty=format:%ct --quiet -1 HEAD",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
        universal_newlines=True,
    )
    try:
        raw_unix_ts = git_log.communicate()[0]
        timestamp = datetime.datetime.utcfromtimestamp(int(raw_unix_ts))
        return timestamp.strftime("%Y%m%d%H%M%S")
    except ValueError:
        return None
