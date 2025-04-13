"""
Aki - An advanced AI assistant framework.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("aki")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "0.0.0"
