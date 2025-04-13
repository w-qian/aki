"""Environment configuration handling for Aki."""

import os
import logging
from typing import Dict, Optional

from .paths import get_env_file

logger = logging.getLogger(__name__)


def load_env_variables() -> Dict[str, str]:
    """Load environment variables from ~/.aki/.env file.

    Returns:
        Dictionary of environment variables loaded from the file
    """
    env_vars = {}
    env_path = get_env_file()

    if env_path.exists():
        try:
            logger.debug(f"Loading environment from {env_path}")
            with open(env_path) as f:
                env_content = f.read()
                env_vars = dict(
                    line.split("=", 1)
                    for line in env_content.splitlines()
                    if "=" in line and not line.strip().startswith("#")
                )
        except Exception as e:
            logger.warning(f"Error reading {env_path}: {e}")
    else:
        logger.debug(f"Environment file not found: {env_path}")

    return env_vars


def get_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a configuration value from system env or ~/.aki/.env file.

    First checks if the variable is set in the system environment,
    then falls back to the .env file if available.

    Args:
        key: The environment variable name
        default: Default value if the variable is not found

    Returns:
        The value of the environment variable, or the default value if not found
    """
    # First check system environment
    value = os.environ.get(key)
    if value is not None:
        return value

    # Then check .env file
    env_vars = load_env_variables()
    return env_vars.get(key, default)
