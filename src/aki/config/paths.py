"""Path utilities for Aki configuration."""

from pathlib import Path


def get_aki_home() -> Path:
    """Get the Aki home directory path.

    Returns:
        Path to the ~/.aki directory, creating it if it doesn't exist
    """
    home = Path.home()
    aki_dir = home / ".aki"
    aki_dir.mkdir(exist_ok=True)
    return aki_dir


def get_env_file() -> Path:
    """Get the path to the environment configuration file.

    Returns:
        Path to the ~/.aki/.env file
    """
    return get_aki_home() / ".env"


def get_default_mcp_settings_path() -> Path:
    """Get the path to the default MCP settings file.

    First checks if the file exists in aki_home, then falls back to the package dir.
    No file copying is performed.

    Returns:
        Path to the mcp_settings.default.json file
    """
    # First try the user's aki_home directory
    user_default_path = get_aki_home() / "mcp_settings.default.json"
    if user_default_path.exists():
        return user_default_path

    # Fallback to the package directory (relative to this file)
    package_path = Path(__file__).parent / "mcp_settings.default.json"
    return package_path
