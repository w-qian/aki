"""Agent-based chat profile implementations."""

from typing import Type
from ...base.agent_profile import AgentProfile


def create_agent_profile(profile_name: str) -> Type[AgentProfile]:
    """Create a new agent profile class.

    Args:
        profile_name: Name of the profile to create

    Returns:
        A new AgentProfile subclass configured for the profile
    """
    return type(
        f"{profile_name.capitalize()}Profile",
        (AgentProfile,),
        {
            "_profile_name": profile_name,
            "__module__": "aki.chat.implementations.agent",
        },
    )
