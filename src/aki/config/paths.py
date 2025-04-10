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