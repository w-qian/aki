#!/usr/bin/env python3
"""MCP server checker for installation and runtime verification."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from aki.tools.mcp.client import McpClientManager
from aki.config.constants import MCP_SERVERS_KEY
from aki.tools.mcp.installation.manager import InstallationManager
from aki.config.paths import get_aki_home, get_default_mcp_settings_path

# Global settings
SKIP_MCP_INSTALL = os.environ.get("SKIP_MCP_INSTALL", "").lower() in (
    "1",
    "true",
    "yes",
)
SKIP_MCP_SERVERS = os.environ.get("SKIP_MCP_SERVERS", "").split(",")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_check")


class ServerChecker:
    """Handles MCP server installation and verification."""

    def __init__(self, config_path: Path):
        """Initialize with config path."""
        self.config_path = config_path
        self.state_file = get_aki_home() / "mcp_server_state.json"
        self.state: Dict[str, Dict] = self._load_state()

    def _load_state(self) -> Dict:
        """Load current server state."""
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text())
                # If format is incorrect, treat as new
                if "initialized_servers" not in state:
                    logger.debug(
                        "State file has incorrect format, creating fresh state"
                    )
                    return {"initialized_servers": {}}
                return state
            except json.JSONDecodeError:
                logger.warning("Invalid state file JSON, starting fresh")
        return {"initialized_servers": {}}

    def _save_state(self):
        """Save current server state."""
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def _update_server_state(self, name: str, success: bool):
        """Update state for a single server."""
        self.state["initialized_servers"][name] = success
        self._save_state()

    async def check_server(self, name: str, config: Dict) -> bool:
        """Check and initialize a single server.

        1. Verify/perform installation
        2. Test server connection
        3. Update state file

        Args:
            name: Server identifier
            config: Server configuration dictionary

        Returns:
            bool: True if server check succeeded, False otherwise
        """
        logger.debug(f"\nChecking server: {name}")

        # Validate required configuration
        if not isinstance(config, dict):
            logger.error(f"[{name}] Invalid server configuration format")
            return False

        try:
            # 1. Installation check/setup with timeout
            try:
                # Set a timeout for the installation check and install process
                return await asyncio.wait_for(
                    self._check_and_install_server(name, config), timeout=20
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"[{name}] Server initialization timed out after 20 seconds"
                )
                return False

        except Exception as e:
            logger.error(f"[{name}] Server check failed with error: {str(e)}")
            logger.debug(f"[{name}] Full error details:", exc_info=True)
            return False

    async def _check_and_install_server(self, name: str, config: Dict) -> bool:
        """Internal method to check and install a server with proper error handling.

        Args:
            name: Server identifier
            config: Server configuration dictionary

        Returns:
            bool: True if server check succeeded, False otherwise
        """
        try:
            # 1. Installation check/setup
            logger.debug(f"[{name}] Creating installation manager...")
            install_manager = InstallationManager(
                name=name,
                check_install_script=config.get("check_install_script"),
                install_scripts=config.get("install_scripts", []),
            )
            logger.debug(
                f"[{name}] Check install script: {config.get('check_install_script')}"
            )
            logger.debug(f"[{name}] Install scripts: {config.get('install_scripts')}")

            logger.debug(f"[{name}] ===> CHECKING IF MCP SERVER IS INSTALLED...")
            logger.debug(f"[{name}] This should take less than 5 seconds")
            check_start_time = asyncio.get_event_loop().time()
            installation_check = install_manager.check_installation()
            check_duration = asyncio.get_event_loop().time() - check_start_time
            logger.debug(
                f"[{name}] Check completed in {check_duration:.2f} seconds, result: {installation_check}"
            )

            if not installation_check:
                logger.info(f"[{name}] ===> MCP SERVER NOT INSTALLED")
                logger.info(
                    f"[{name}] ===> STARTING INSTALLATION - THIS MAY TAKE UP TO 2 MINUTES..."
                )
                install_start_time = asyncio.get_event_loop().time()
                if not install_manager.install():
                    install_duration = (
                        asyncio.get_event_loop().time() - install_start_time
                    )
                    logger.error(
                        f"[{name}] Installation failed after {install_duration:.2f} seconds"
                    )
                    return False
                install_duration = asyncio.get_event_loop().time() - install_start_time
                logger.info(
                    f"[{name}] ===> INSTALLATION COMPLETED SUCCESSFULLY in {install_duration:.2f} seconds"
                )

            # 2. Test server connection
            logger.debug(f"[{name}] Getting MCP client...")
            logger.debug(f"[{name}] Using config path: {self.config_path}")

            # Get client with timeout to avoid blocking
            try:
                client_manager = McpClientManager.get_instance(
                    config_path=str(self.config_path)
                )
                client = client_manager.get_client(name)
                if not client:
                    logger.error(f"[{name}] Failed to get MCP client")
                    return False
                logger.debug(f"[{name}] Successfully got MCP client")
            except Exception as e:
                logger.error(f"[{name}] Failed to initialize client: {str(e)}")
                return False

            # # Test tool listing
            # try:
            #     logger.debug(
            #         f"[{name}] Testing server connection by listing tools (timeout: 5s)..."
            #     )
            #     # Add a 5-second timeout for the list_tools call
            #     tools = await asyncio.wait_for(client.list_tools(), timeout=5)
            #     logger.debug(f"[{name}] Successfully listed {len(tools)} tools")
            #     for tool in tools:
            #         logger.debug(f"[{name}] Available tool: {tool['name']}")
            #     return True
            # except asyncio.TimeoutError:
            #     logger.error(f"[{name}] Connection timed out after 5s")
            #     return False
            # except Exception as e:
            #     logger.error(f"[{name}] Failed to list tools: {str(e)}")
            #     logger.debug(f"[{name}] Tool listing error details:", exc_info=True)
            #     return False

        except Exception as e:
            logger.error(f"[{name}] Server check failed with error: {str(e)}")
            logger.debug(f"[{name}] Full error details:", exc_info=True)
            return False

    async def check_all_servers(self) -> bool:
        """Check all servers in config.

        Returns:
            bool: True if all critical servers initialized successfully
        """
        try:
            # Load server configurations
            logger.debug(f"Loading MCP server configurations from: {self.config_path}")
            if not self.config_path.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")

            with open(self.config_path) as f:
                try:
                    config = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in server config: {str(e)}")
                    return False

            servers = config.get(MCP_SERVERS_KEY, {})
            logger.debug(f"Found {len(servers)} servers in config")
            logger.debug(f"Server names: {list(servers.keys())}")

            tasks = []
            for name, server_config in servers.items():
                if server_config.get("disabled", False):
                    logger.debug(f"Skipping disabled server: {name}")
                    continue

                # Create tasks for all servers to allow concurrent initialization
                tasks.append((name, server_config))

            # Check for configuration to skip installation
            if SKIP_MCP_INSTALL:
                logger.info(
                    "MCP server installation checks skipped due to SKIP_MCP_INSTALL=1"
                )

            # Process each server with its own timeout and error handling
            for name, server_config in tasks:
                # Skip servers listed in SKIP_MCP_SERVERS environment variable
                if name in SKIP_MCP_SERVERS:
                    logger.warning(
                        f"Skipping server: {name} (listed in SKIP_MCP_SERVERS)"
                    )
                    self._update_server_state(name, False)
                    continue

                logger.debug(f"\n{'='*50}")
                logger.debug(f"Processing server: {name}")
                logger.debug(f"{'='*50}")

                try:
                    # Process with timeout but don't allow one server to block others
                    success = False
                    try:
                        # Give enough time for server check (especially for server initialization)
                        logger.debug(f"Checking server {name} with 30s timeout")
                        success = await asyncio.wait_for(
                            self.check_server(name, server_config), timeout=30
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Check for server {name} timed out after 30 seconds"
                        )
                        success = False
                    except Exception as e:
                        logger.error(f"Error checking server {name}: {str(e)}")
                        logger.debug("Full error details:", exc_info=True)
                        success = False

                    self._update_server_state(name, success)
                    logger.debug(
                        f"MCP Server {name} check result: {'SUCCESS' if success else 'FAILED'}"
                    )
                    if not success:
                        logger.warning(
                            f"Server {name} failed initialization but will not block other servers"
                        )
                except Exception as e:
                    logger.error(f"Unexpected error processing server {name}: {e}")
                    # Continue with next server regardless of errors

            logger.debug("\nFinal Results:")
            logger.debug(
                "MCP initialization complete with some servers potentially unavailable"
            )
            logger.debug(f"Current state: {json.dumps(self.state, indent=2)}")
            # Always return True so application startup isn't blocked
            return True

        except Exception as e:
            logger.error(f"Failed to check servers: {e}")
            return False


async def _check_servers_with_timeout(config_path: Path, timeout: int = 30) -> bool:
    """Run server checks with a timeout.

    Args:
        config_path: Path to MCP config.
        timeout: Timeout in seconds.

    Returns:
        bool: True if checks completed, False if timed out
    """
    try:
        checker = ServerChecker(config_path)
        # Set an overall timeout for all server checks
        await asyncio.wait_for(checker.check_all_servers(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        logger.warning(
            f"MCP server initialization timed out after {timeout} seconds - installation may still be in progress"
        )
        return False
    except Exception as e:
        logger.error(f"Unexpected error in server checks: {str(e)}")
        logger.debug("Full error details:", exc_info=True)
        return False


def check_servers(config_path: Optional[Path] = None) -> bool:
    """Check all MCP servers with timeouts to prevent blocking application startup.

    Args:
        config_path: Path to MCP config. If None, uses default location.

    Returns:
        bool: Always returns True to avoid blocking application startup
    """
    try:

        if config_path is None:
            config_path = get_default_mcp_settings_path()

        logger.debug(f"Starting MCP server checks with config: {config_path}")
        logger.debug(f"Current working directory: {Path.cwd()}")

        if not config_path.exists():
            logger.error(f"Config file does not exist: {config_path}")
            return True  # Still return True to avoid blocking

        # Increase timeout for overall server check process
        asyncio.run(
            _check_servers_with_timeout(config_path, timeout=180)
        )  # 3 minute timeout

        logger.debug("MCP server checks completed")
        return True

    except Exception as e:
        logger.error(f"Unexpected error in check_servers: {str(e)}")
        logger.debug("Full error details:", exc_info=True)
        return False


if __name__ == "__main__":
    success = check_servers()
    if not success:
        logger.warning("Some critical servers failed initialization")
