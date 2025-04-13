"""Factory for creating chat profile instances."""

import logging
from typing import Dict, Type
from .base.base_profile import BaseProfile
from .profile_registry import ProfileRegistry

logger = logging.getLogger(__name__)


class ProfileFactory:
    """Factory for creating chat profile instances."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ProfileFactory, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the profile factory.

        Args:
            usage_metrics: Optional UsageMetrics instance for token tracking.
                          If provided, it will be passed to all created profiles.
        """
        if not self._initialized:
            # Initialize ProfileManager first as it loads the profiles
            from ..config.profile_manager import ProfileManager

            self.profile_manager = ProfileManager()
            self.registry = ProfileRegistry()
            ProfileFactory._initialized = True
            logger.debug("ProfileFactory initialized")

    def get_default_profile(self) -> str:
        """Get the name of the default chat profile.

        Returns the last profile (typically a custom profile) that has default=True.
        This prioritizes custom profiles over built-in ones when multiple have default=True.
        """
        default_profile = None
        for name, info in self.registry.get_all_profiles().items():
            if hasattr(info.implementation, "chat_profile"):
                profile = info.implementation.chat_profile()
                if getattr(profile, "default", False):
                    default_profile = info.internal_name

        # Return the last default profile found, or first available profile if none is default
        return (
            default_profile
            or next(iter(self.registry.get_all_profiles().values())).internal_name
        )

    def get_available_profiles(self) -> Dict[str, Type[BaseProfile]]:
        """Get all available chat profiles."""
        return {
            name: info.implementation
            for name, info in self.registry.get_all_profiles().items()
        }

    def create_profile(self, name: str) -> BaseProfile:
        """Create a chat profile instance.

        Args:
            name: Name of the profile to create (can be internal name or display name)

        Returns:
            An instance of the requested chat profile

        Raises:
            ValueError: If profile name not found
        """
        info = self.registry.get_profile_info(name)
        if not info:
            available = [
                p.profile_name for p in self.registry.get_all_profiles().values()
            ]
            raise ValueError(
                f"Profile '{name}' not found. Available profiles: {available}"
            )

        logger.debug(
            f"Creating profile instance: {info.internal_name} ({info.profile_type})"
        )

        try:
            profile_instance = None

            # Create instance based on profile type
            if info.profile_type == "supervisor":
                profile_instance = info.implementation()
            else:
                profile_instance = info.implementation(info.internal_name)

            return profile_instance

        except Exception as e:
            logger.error(f"Failed to create profile instance for {name}: {e}")
            raise
