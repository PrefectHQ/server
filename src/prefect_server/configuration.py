import os

import prefect_server
from prefect.configuration import load_configuration
from prefect.utilities.plugins import register_plugin

DEFAULT_CONFIG = os.path.join(os.path.dirname(prefect_server.__file__), "config.toml")
USER_CONFIG = os.getenv(
    "PREFECT_SERVER__USER_CONFIG_PATH", "~/.prefect_server/config.toml"
)
ENV_VAR_PREFIX = "PREFECT_SERVER"


config = load_configuration(
    path=DEFAULT_CONFIG, user_config_path=USER_CONFIG, env_var_prefix=ENV_VAR_PREFIX
)


@register_plugin("get_backend_config")
def get_backend_config():
    return config
