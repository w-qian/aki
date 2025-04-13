"""Logging configuration."""

import logging
import logging.config
import os
from datetime import datetime
import yaml
from aki.config.paths import get_aki_home


def setup_logging():
    """Set up logging configuration from YAML file."""
    # Get project root directory (2 levels up from this file)
    aki_home = get_aki_home()

    # Ensure .log directory exists in project root
    log_dir = os.path.join(aki_home, ".log")
    os.makedirs(log_dir, exist_ok=True)

    # Load configuration from YAML file
    config_path = os.path.join(os.path.dirname(__file__), "logging.yaml")

    if os.path.exists(config_path):
        with open(config_path, "rt") as f:
            config = yaml.safe_load(f)

        # Update log file path to use project root with datetime in filename
        log_filename = datetime.now().strftime("aki_debug_%Y%m%d_%H.log")
        config["handlers"]["debug_file"]["filename"] = os.path.join(
            log_dir, log_filename
        )

        # Ensure we're not disabling existing loggers
        config["disable_existing_loggers"] = False

        try:
            # Reset any existing logging configuration
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)

            # Configure logging
            logging.config.dictConfig(config)
            logging.debug("Logging configuration initialized from YAML")
            logging.debug(
                f"Log file location: {config['handlers']['debug_file']['filename']}"
            )
        except Exception as e:
            logging.error(f"Error configuring logging: {e}")
            raise
    else:
        logging.basicConfig(level=logging.DEBUG)
        logging.warning(
            f"Logging config file not found at {config_path}, using basic configuration"
        )
