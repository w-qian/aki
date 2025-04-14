"""Initialize Aki configuration and services."""

import shutil
import sys
from pathlib import Path
import logging
import os
from aki.config import constants
from aki.config.paths import get_aki_home, get_env_file
from dotenv import load_dotenv

logger = logging.getLogger("aki-install")


def initialize_mcp_settings():
    """Initialize MCP settings from template."""
    aki_dir = get_aki_home()
    template_path = Path(__file__).parent / "config" / "mcp_settings.template.json"
    settings_path = aki_dir / "mcp_settings.json"

    if not settings_path.exists() and template_path.exists():
        shutil.copy2(template_path, settings_path)
        logger.info(f"Initialized MCP settings at {settings_path}")


def ensure_env_variables_updated() -> None:
    """Ensure .env file exists. If not, create from template.
    If it already exists, leave it unchanged to preserve user customizations."""

    aki_dir = get_aki_home()
    env_path = aki_dir / ".env"
    template_path = Path(__file__).parent / "config" / ".env.example"

    if not template_path.exists():
        logger.warning(f"No .env.example found at {template_path}")
        return

    # If no .env file exists, simply create one from template
    if not env_path.exists():
        shutil.copy2(template_path, env_path)
        logger.info(f"Created new .env file at {env_path}")
        return

    # If .env already exists, don't modify it
    logger.debug(
        f".env file already exists at {env_path}, preserving all user settings"
    )


def validate_and_set_token_threshold() -> None:
    """Validate and set the token threshold configuration.
    Clamps values to valid range and updates environment variable."""
    MIN_THRESHOLD = 30000
    MAX_THRESHOLD = 200000
    DEFAULT_THRESHOLD = constants.DEFAULT_TOKEN_THRESHOLD

    threshold_str = os.getenv("AKI_TOKEN_THRESHOLD")
    if threshold_str:
        try:
            threshold = int(threshold_str)
            if threshold < MIN_THRESHOLD:
                logger.warning(
                    f"AKI_TOKEN_THRESHOLD {threshold} is below minimum. Using {MIN_THRESHOLD}"
                )
                threshold = MIN_THRESHOLD
            elif threshold > MAX_THRESHOLD:
                logger.warning(
                    f"AKI_TOKEN_THRESHOLD {threshold} exceeds maximum. Using {MAX_THRESHOLD}"
                )
                threshold = MAX_THRESHOLD
        except ValueError:
            logger.warning(
                f"Invalid AKI_TOKEN_THRESHOLD value. Using default {DEFAULT_THRESHOLD}"
            )
            threshold = DEFAULT_THRESHOLD
    else:
        threshold = DEFAULT_THRESHOLD

    # Update environment variable with validated value
    os.environ["AKI_TOKEN_THRESHOLD"] = str(threshold)


def initialize_aki():
    """Initialize Aki configuration and services."""
    logger.debug("Starting Aki initialization...")

    root_path = str(Path(__file__).parent)
    os.environ["CHAINLIT_APP_ROOT"] = root_path
    # If chainlit is already imported, patch it
    if "chainlit.config" in sys.modules:
        logger.debug("Patching chainlit config")
        sys.modules["chainlit.config"].APP_ROOT = root_path

    # To disable tokenizer warning
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    # Create base directory
    aki_dir = get_aki_home()
    aki_dir.mkdir(exist_ok=True)

    # Ensure .env file is up to date with template
    # (should run before loading environment variables)
    ensure_env_variables_updated()

    # Load environment variables from the updated .env file
    load_dotenv(get_env_file())

    # Validate and set token threshold
    validate_and_set_token_threshold()

    # Initialize MCP settings if needed
    initialize_mcp_settings()
