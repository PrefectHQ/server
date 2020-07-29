import sys as _sys

if _sys.version_info < (3, 7):
    raise ImportError("Prefect Server requires Python 3.7+.")

from prefect_server.configuration import config

import prefect_server.utilities
from prefect_server.utilities.plugins import API as api, PLUGINS as plugins
import prefect_server.database
import prefect_server._api

# after server has loaded, import any plugins
prefect_server.utilities.plugins.import_plugins()

# -------------------------------------------
# versioneer - automatic versioning
from ._version import get_versions

try:
    __version__ = get_versions()["version"]
except Exception:
    __version__ = "0+unknown"

del get_versions
