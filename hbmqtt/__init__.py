import warnings

from amqtt import __version__
from amqtt import *

warnings.warn("importing hbmqtt is deprecated. Please import amqtt", DeprecationWarning)
