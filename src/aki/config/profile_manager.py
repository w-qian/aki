"""Profile management for Aki agents."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
import chainlit as cl
from langchain.tools import BaseTool
from aki.tools import create_web_search_tool
from aki.tools import create_think_tool
from ..tools.code_analyzer.code_analyzer import create_code_analyzer_tool
from ..tools.file_management.toolkit import FileManagementToolkit
from ..tools.command_executor import create_shell_command_tool
from ..tools.render_html import create_render_html_tool
from ..tools.tasklist_manager import create_tasklist_tool
from ..tools.time import create_datetime_now_tool
from ..tools.mcp import create_mcp_tools_sync
from ..tools.code_executor import create_execute_python_tool
from ..tools.process_manager import create_process_manager_tool
from aki.tools.render_mermaid import create_render_mermaid_tool
from .paths import get_aki_home, get_default_mcp_settings_path

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages agent profiles including tools and system prompts."""

    _instance = None
    _initialized = False

    BUILTIN_PROFILES = {"aki", "akira", "akisa"}
    BUILTIN_PROFILES_PATH_ENV_VAR = "AKI_BUILTIN_PROFILES_PATH"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProfileManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            from ..chat.profile_registry import ProfileRegistry

            self.registry = ProfileRegistry()
            self.config_dir = get_aki_home()
            self.package_dir = Path(__file__).parent.parent
            self.builtin_profiles_dir = self._get_builtin_profiles_dir()
            self.profiles = {}
            self._tool_factories = self._init_tool_factories()
            self._load_profiles()
            ProfileManager._initialized = True

    def _get_builtin_profiles_dir(self) -> Path:
        """Get the directory containing built-in profiles."""
        # Check environment variable first
        custom_dir = os.environ.get(self.BUILTIN_PROFILES_PATH_ENV_VAR)
        if custom_dir and os.path.isdir(custom_dir):
            logger.info(f"Using custom built-in profiles directory: {custom_dir}")
            return Path(custom_dir)

        # Default to package directory
        return self.package_dir / "profiles"

    def set_builtin_profiles_dir(self, directory_path: str) -> None:
        """Set the directory containing built-in profiles.

        Args:
            directory_path: Path to directory containing built-in profile files

        Raises:
            ValueError: If directory doesn't exist
        """
        path = Path(directory_path)
        if not path.is_dir():
            raise ValueError(
                f"Built-in profiles directory does not exist: {directory_path}"
            )

        self.builtin_profiles_dir = path
        # Reload profiles
        self._load_profiles()

    def _init_tool_factories(self) -> Dict[str, callable]:
        """Initialize mapping of tool names to their factory functions."""
        file_toolkit = FileManagementToolkit()
        return {
            # Special file management sets
            "file_management_full": file_toolkit.get_tools,
            "file_management_readonly": file_toolkit.get_read_only_tools,
            # Individual tools
            "shell_command": create_shell_command_tool,
            "render_html": create_render_html_tool,
            "code_analyzer": create_code_analyzer_tool,
            "web_search": create_web_search_tool,
            "tasklist": create_tasklist_tool,
            "python_executor": create_execute_python_tool,
            "get_datetime_now": create_datetime_now_tool,
            "process_manager": create_process_manager_tool,
            "think": create_think_tool,
            "render_mermaid": create_render_mermaid_tool,
        }

    def _load_profiles(self):
        """Load all available profiles."""
        logger.debug("Starting to load profiles")

        # Reset profiles dict for reloading
        self.profiles = {}

        # Load built-in agent profiles
        # Modified to use self.builtin_profiles_dir instead of self.package_dir / "profiles"
        logger.debug(f"Loading profiles from: {self.builtin_profiles_dir}")
        for profile in self.BUILTIN_PROFILES:
            path = self.builtin_profiles_dir / f"{profile}.json"
            try:
                with open(path) as f:
                    config = json.load(f)
                    profile_name = config["name"]
                    # Add underscore only if names match
                    internal_name = (
                        f"_{profile}" if profile == profile_name else profile
                    )
                    self.profiles[internal_name] = config  # Store with internal_name
                    self.registry.register_agent_profile(
                        internal_name=internal_name,
                        profile_name=profile_name,
                        config_path=str(path),
                        is_default=config.get("default", False),
                        order=self._get_profile_order(profile, config),
                    )
            except Exception as e:
                logger.error(f"Failed to load built-in profile {profile}: {e}")

        # Load user profiles
        user_profiles_dir = self.config_dir / "profiles"
        if user_profiles_dir.exists():
            for path in user_profiles_dir.glob("*.json"):
                profile_name = path.stem
                if (
                    profile_name not in self.BUILTIN_PROFILES
                ):  # Don't allow overriding built-in profiles
                    try:
                        with open(path) as f:
                            config = json.load(f)
                            profile_name = config["name"]
                            # Add underscore only if names match
                            internal_name = (
                                f"_{profile_name}"
                                if profile_name == profile_name
                                else profile_name
                            )
                            self.profiles[internal_name] = (
                                config  # Store with internal_name
                            )
                            self.registry.register_agent_profile(
                                internal_name=internal_name,
                                profile_name=profile_name,
                                config_path=str(path),
                                is_default=config.get("default", False),
                                order=self._get_profile_order(profile_name, config),
                            )
                    except Exception as e:
                        logger.error(f"Failed to load user profile {profile_name}: {e}")

        # Register supervisor profiles
        from ..chat.implementations.supervisor.aki_team import AkiTeamProfile

        self.registry.register_supervisor_profile(
            "aki_team", AkiTeamProfile, order=40.0
        )

    def _get_mcp_settings(self) -> Dict[str, dict]:
        """Get merged MCP settings from default and user config."""
        mcp_settings = {"mcpServers": {}}

        # Load default settings
        default_path = get_default_mcp_settings_path()
        if default_path.exists():
            try:
                with open(default_path) as f:
                    default_config = json.load(f)
                    mcp_settings["mcpServers"].update(
                        default_config.get("mcpServers", {})
                    )
            except Exception as e:
                logger.error(f"Failed to load default MCP settings: {e}")

        # Load user settings
        user_path = self.config_dir / "mcp_settings.json"
        if user_path.exists():
            try:
                with open(user_path) as f:
                    user_config = json.load(f)
                    # User settings override defaults
                    mcp_settings["mcpServers"].update(user_config.get("mcpServers", {}))
            except Exception as e:
                logger.error(f"Failed to load user MCP settings: {e}")

        return mcp_settings

    def get_tools(self, profile_name: str) -> List[BaseTool]:
        """Get all tools for a profile."""
        # Try to get profile info from registry first
        info = self.registry.get_profile_info(profile_name)
        if info:
            profile_name = info.internal_name  # Use internal name for lookup

        if profile_name not in self.profiles:
            raise ValueError(
                f"Profile '{profile_name}' not found. Available: {list(self.profiles.keys())}"
            )

        profile = self.profiles[profile_name]
        tools = []
        use_batch_tool = False

        # Create tools
        for tool_name in profile.get("tools", []):
            if tool_name == "batch_tool":
                use_batch_tool = True
                continue  # Skip it for now, we'll add it at the end
            elif tool_name in self._tool_factories:
                try:
                    tool = self._tool_factories[tool_name]()
                    if isinstance(tool, list):
                        tools.extend(tool)
                    else:
                        tools.append(tool)
                except Exception as e:
                    logger.warning(f"Failed to create tool {tool_name}: {e}")

        # Create MCP tools
        enabled_servers = profile.get("enabled_mcp_servers", [])
        if enabled_servers:
            try:
                # Get all available MCP settings
                mcp_settings = self._get_mcp_settings()

                # Filter servers based on profile configuration
                filtered_settings = {"mcpServers": {}}
                if enabled_servers == "__ALL__":
                    # For Aki, use all available servers
                    filtered_settings = mcp_settings
                else:
                    # For other profiles, only use specifically enabled servers
                    for server_name in enabled_servers:
                        if server_name in mcp_settings["mcpServers"]:
                            filtered_settings["mcpServers"][server_name] = mcp_settings[
                                "mcpServers"
                            ][server_name]

                # Create MCP tools directly from settings
                if filtered_settings["mcpServers"]:
                    # Process variables in args
                    workspace = str(self.package_dir.parent.parent)
                    user_home = str(Path.home())
                    for config in filtered_settings["mcpServers"].values():
                        args = config.get("args", [])
                        config["args"] = [
                            arg.replace("${workspace}", workspace).replace(
                                "${user_home}", user_home
                            )
                            for arg in args
                        ]

                    mcp_tools = create_mcp_tools_sync(filtered_settings)
                    tools.extend(mcp_tools)
            except Exception as e:
                logger.warning(f"Failed to create MCP tools for {profile_name}: {e}")

        # Add batch tool at the end if requested
        if use_batch_tool:
            try:
                from ..tools.batch_tool import create_batch_tool

                # Create a dictionary of all available tools
                tools_dict = {tool.name: tool for tool in tools}

                # Create the batch tool with all available tools
                batch_tool = create_batch_tool(tools_dict)
                tools.append(batch_tool)
                logger.debug(f"Added batch_tool with access to {len(tools_dict)} tools")
            except Exception as e:
                logger.warning(f"Failed to create batch_tool: {e}")

        return tools

    def get_chat_profile(self, profile_name: str) -> cl.ChatProfile:
        """Get chat profile configuration."""
        # Try to get profile info from registry first
        info = self.registry.get_profile_info(profile_name)
        if info:
            profile_name = info.internal_name  # Use internal name for lookup

        if profile_name not in self.profiles:
            raise ValueError(
                f"Profile '{profile_name}' not found. Available: {list(self.profiles.keys())}"
            )

        profile = self.profiles[profile_name]
        return cl.ChatProfile(
            name=profile["name"],
            markdown_description=profile["description"],
            default=profile.get("default", False),
            starters=[cl.Starter(**starter) for starter in profile.get("starters", [])],
        )

    def get_system_prompt(self, profile_name: str) -> str:
        """Get system prompt for a profile."""
        # Try to get profile info from registry first
        info = self.registry.get_profile_info(profile_name)
        if info:
            profile_name = info.internal_name  # Use internal name for lookup

        if profile_name not in self.profiles:
            raise ValueError(
                f"Profile '{profile_name}' not found. Available: {list(self.profiles.keys())}"
            )

        profile = self.profiles[profile_name]
        logger.debug(f"Getting system prompt for {profile_name}")

        # Check if profile uses a prompt file
        if "system_prompt_file" in profile:
            if self.is_builtin_profile(profile_name):
                # Modified to use self.builtin_profiles_dir instead of self.package_dir
                package_prompt_path = (
                    self.builtin_profiles_dir / profile["system_prompt_file"]
                )
                try:
                    with open(package_prompt_path) as f:
                        return f.read()
                except Exception as e:
                    logger.error(
                        f"Failed to load package prompt file for {profile_name}: {e}"
                    )
            user_prompt_path = (
                self.config_dir / "profiles" / profile["system_prompt_file"]
            )
            if user_prompt_path.exists():
                try:
                    with open(user_prompt_path) as f:
                        return f.read()
                except Exception as e:
                    logger.error(
                        f"Failed to load user prompt file for {profile_name}: {e}"
                    )
            # Fallback to inline prompt if available
            return self._get_inline_prompt(profile)
        else:
            # Use inline prompt from JSON if no file specified
            return self._get_inline_prompt(profile)

    def get_rules_content(self, profile_name: str) -> Optional[str]:
        """Get rules content for a profile if defined."""
        # Try to get profile info from registry first
        info = self.registry.get_profile_info(profile_name)
        if info:
            profile_name = info.internal_name  # Use internal name for lookup

        if profile_name not in self.profiles:
            return None

        profile = self.profiles[profile_name]
        if "rules_file" not in profile:
            return None

        # Load rules from file
        if self.is_builtin_profile(profile_name):
            # Modified to use self.builtin_profiles_dir instead of self.package_dir
            package_rules_path = self.builtin_profiles_dir / profile["rules_file"]
            try:
                with open(package_rules_path) as f:
                    return f.read()
            except Exception as e:
                logger.error(
                    f"Failed to load package rules file for {profile_name}: {e}"
                )

        # Try user-defined rules
        user_rules_path = self.config_dir / "profiles" / profile["rules_file"]
        if user_rules_path.exists():
            try:
                with open(user_rules_path) as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to load user rules file for {profile_name}: {e}")

        return None

    def _get_inline_prompt(self, profile: dict) -> str:
        """Get inline prompt from profile JSON."""
        prompt = profile.get("system_prompt", "")
        # Handle both string and list formats
        if isinstance(prompt, list):
            return "\n".join(prompt)
        return prompt

    def get_profile_names(self) -> List[str]:
        """Get list of available profile names."""
        return list(self.profiles.keys())

    def _get_profile_order(self, profile_name: str, config: dict = None) -> float:
        """Get the display order for a profile.

        Args:
            profile_name: Name of the profile
            config: Optional profile configuration dict

        Returns:
            Order value as a float (lower values appear first)
        """
        # If config is provided and contains order_id, use that first
        if config and "order_id" in config:
            try:
                # Support for numeric order_id including floats
                return float(config["order_id"])
            except (ValueError, TypeError):
                # If order_id isn't a valid number, fall back to default ordering
                pass

        # Built-in profiles have predefined order if no explicit order_id is set
        order_map = {
            "aki": 10,  # Aki first
            "akira": 20,  # Then specialists
            "akisa": 30,
        }
        return float(order_map.get(profile_name, 100))  # Custom profiles at end

    def is_builtin_profile(self, profile_name: str) -> bool:
        """Check if a profile is built-in."""
        return profile_name in self.BUILTIN_PROFILES

    def get_profile_config(self, profile_name: str) -> Dict:
        """Get complete profile configuration.

        Args:
            profile_name: Name of the profile

        Returns:
            Dict containing the complete profile configuration

        Raises:
            ValueError: If profile is not found
        """
        # Try to get profile info from registry first
        info = self.registry.get_profile_info(profile_name)
        if info:
            profile_name = info.internal_name  # Use internal name for lookup

        if profile_name not in self.profiles:
            raise ValueError(
                f"Profile '{profile_name}' not found. Available: {list(self.profiles.keys())}"
            )

        return self.profiles[profile_name]
