"""Central registry for chat profiles."""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Type
from .base.base_profile import BaseProfile

logger = logging.getLogger(__name__)


@dataclass
class ProfileInfo:
    """Information about a chat profile."""

    internal_name: str  # Internal identifier (e.g., '_aki' if matches profile_name)
    profile_name: str  # Profile name (e.g., 'Aki - Ask me anything')
    profile_type: str  # 'agent' or 'supervisor'
    implementation: Type  # Profile implementation class
    config_path: Optional[str]  # Path to config file (for agent profiles)
    is_default: bool = False  # Whether this is the default profile
    order: float = 100.0  # Order for display (lower numbers first)


class ProfileRegistry:
    """Central registry for all profile information."""

    _instance = None
    _profiles: Dict[str, ProfileInfo] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._profiles = (
                {}
            )  # Initialize in __new__ to ensure single instance
            logger.debug("Created new ProfileRegistry instance")
        return cls._instance

    def register_agent_profile(
        self,
        internal_name: str,
        profile_name: str,
        config_path: str,
        is_default: bool = False,
        order: float = 100.0,
    ):
        """Register an agent profile from configuration."""
        if not internal_name or not profile_name:
            raise ValueError("internal_name and profile_name are required")

        if not config_path or not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        # Check for duplicate names
        if internal_name in self._profiles:
            raise ValueError(
                f"Profile with internal name '{internal_name}' already exists"
            )
        if profile_name in self._profiles:
            raise ValueError(f"Profile with name '{profile_name}' already exists")

        from .implementations.agent import create_agent_profile

        logger.debug(f"Registering agent profile: {internal_name} ({profile_name})")

        try:
            implementation = create_agent_profile(internal_name)
            info = ProfileInfo(
                internal_name=internal_name,
                profile_name=profile_name,
                profile_type="agent",
                implementation=implementation,
                config_path=config_path,
                is_default=is_default,
                order=order,
            )

            # Validate implementation
            if not hasattr(implementation, "chat_profile"):
                raise ValueError(
                    f"Implementation for {internal_name} missing chat_profile method"
                )

            self._profiles[internal_name] = info
            self._profiles[profile_name] = info
            logger.debug(f"Successfully registered agent profile: {internal_name}")

        except Exception as e:
            error_msg = f"Failed to register agent profile {internal_name}: {str(e)}"
            logger.error(error_msg)
            raise type(e)(error_msg) from e

    def register_supervisor_profile(
        self, internal_name: str, implementation: Type[BaseProfile], order: float = 50.0
    ):
        """Register a supervisor profile."""
        logger.debug(f"Registering supervisor profile: {internal_name}")

        try:
            # Create temporary instance to get display name
            profile = implementation()
            profile_name = profile.chat_profile().name

            # Get default status from profile
            is_default = getattr(profile.chat_profile(), "default", False)

            info = ProfileInfo(
                internal_name=internal_name,
                profile_name=profile_name,
                profile_type="supervisor",
                implementation=implementation,
                config_path=None,
                is_default=is_default,
                order=order,
            )
            self._profiles[internal_name] = info
            self._profiles[profile_name] = info
            logger.debug(
                f"Successfully registered supervisor profile: {internal_name} ({profile_name})"
            )
        except Exception as e:
            logger.error(f"Failed to register supervisor profile {internal_name}: {e}")
            raise

    def get_profile_info(self, name: str) -> Optional[ProfileInfo]:
        """Get profile info by either internal or display name."""
        info = self._profiles.get(name)
        if info:
            logger.debug(f"Found profile info for {name}")
        else:
            logger.debug(f"No profile info found for {name}")
        return info

    def get_all_profiles(self, sort: bool = True) -> Dict[str, ProfileInfo]:
        """Get all registered profiles.

        Args:
            sort: Whether to sort profiles by order and name

        Returns:
            Dict mapping internal names to ProfileInfo objects.
            Only returns unique profiles (no display name duplicates).

        Raises:
            RuntimeError: If no profiles are registered
        """
        if not self._profiles:
            error_msg = "No profiles registered"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            # Get unique profiles (using internal names)
            profiles = {k: v for k, v in self._profiles.items() if k == v.internal_name}

            if not profiles:
                error_msg = "No valid profiles found (internal names don't match)"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            if sort:
                try:
                    # Sort by order first, then by profile name
                    sorted_items = sorted(
                        profiles.items(), key=lambda x: (x[1].order, x[1].profile_name)
                    )
                    profiles = dict(sorted_items)

                except Exception as e:
                    error_msg = f"Error sorting profiles: {str(e)}"
                    logger.error(error_msg)
                    # Fall back to unsorted profiles rather than failing
                    logger.warning("Returning unsorted profiles")

            logger.debug(
                f"Available profiles ({len(profiles)}): {[p.profile_name for p in profiles.values()]}"
            )
            return profiles

        except Exception as e:
            error_msg = f"Error processing profiles: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def debug_status(self):
        """Print debug information about the registry state."""
        logger.debug("=== ProfileRegistry Status ===")
        logger.debug(f"Total profiles: {len(self._profiles)}")
        logger.debug("Registered profiles:")
        for name, info in self._profiles.items():
            logger.debug(f"  - {name} -> {info.profile_name} ({info.profile_type})")
        logger.debug("========================")
