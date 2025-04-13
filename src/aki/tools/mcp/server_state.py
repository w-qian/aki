"""MCP server state management for fast failure detection."""

import json
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, List

from aki.config.paths import get_aki_home

logger = logging.getLogger("aki.tools.mcp.server_state")

# Constants
MAX_RETRY_COUNT = 2  # Maximum number of times to retry a problematic server
FAILURE_EXPIRY = 3600  # How long to remember failures in seconds (1 hour)


class ServerStateManager:
    """Manages state tracking for MCP servers to implement fast-fail detection."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ServerStateManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.state_path = Path(get_aki_home()) / "mcp_server_state.json"
        self.state = self._load_state()
        self._clean_expired_failures()

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file or create default state."""
        try:
            if self.state_path.exists():
                with open(self.state_path, "r") as f:
                    state = json.load(f)

                # Ensure state has the structure we need
                if not isinstance(state, dict):
                    state = {}

                if "initialized_servers" not in state:
                    state["initialized_servers"] = {}

                if "problematic_servers" not in state:
                    state["problematic_servers"] = {}

                return state
            else:
                # Create default state structure
                return {"initialized_servers": {}, "problematic_servers": {}}

        except Exception as e:
            logger.error(f"Error loading server state: {e}")
            return {"initialized_servers": {}, "problematic_servers": {}}

    def _save_state(self) -> None:
        """Save current state to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)

            with open(self.state_path, "w") as f:
                json.dump(self.state, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving server state: {e}")

    def _clean_expired_failures(self) -> None:
        """Remove expired failure records."""
        now = time.time()
        problematic = self.state.get("problematic_servers", {})
        expired = []

        for server, info in problematic.items():
            last_failure = info.get("last_failure", 0)
            if now - last_failure > FAILURE_EXPIRY:
                expired.append(server)

        for server in expired:
            logger.debug(f"Clearing expired failure record for {server}")
            if server in problematic:
                del problematic[server]

        if expired:
            self._save_state()

    def should_skip_server(self, server_name: str) -> bool:
        """Determine if a server should be skipped based on its failure history.

        Args:
            server_name: Name of the server to check

        Returns:
            bool: True if the server should be skipped, False otherwise
        """
        self._clean_expired_failures()
        problematic = self.state.get("problematic_servers", {})

        if server_name in problematic:
            info = problematic[server_name]
            failure_count = info.get("failure_count", 0)

            # Skip if the server has failed too many times
            if failure_count >= MAX_RETRY_COUNT:
                last_failure = info.get("last_failure", 0)
                time_ago = round((time.time() - last_failure) / 60)
                logger.info(
                    f"Skipping problematic server {server_name} (failed {failure_count} times, last failure {time_ago} minutes ago)"
                )
                return True

        return False

    def record_failure(self, server_name: str) -> None:
        """Record a server failure.

        Args:
            server_name: Name of the failed server
        """
        problematic = self.state.setdefault("problematic_servers", {})

        if server_name not in problematic:
            problematic[server_name] = {"failure_count": 1, "last_failure": time.time()}
        else:
            problematic[server_name]["failure_count"] += 1
            problematic[server_name]["last_failure"] = time.time()

        self._save_state()

    def record_success(self, server_name: str) -> None:
        """Record a server success and clear its failure history.

        Args:
            server_name: Name of the successful server
        """
        problematic = self.state.get("problematic_servers", {})

        if server_name in problematic:
            del problematic[server_name]
            self._save_state()

        # Also record in initialized servers
        initialized = self.state.setdefault("initialized_servers", {})
        initialized[server_name] = True
        self._save_state()

    def get_all_problematic_servers(self) -> List[str]:
        """Get a list of all currently problematic servers.

        Returns:
            List[str]: List of problematic server names
        """
        self._clean_expired_failures()
        return list(self.state.get("problematic_servers", {}).keys())


# Singleton instance
_state_manager = None


def get_state_manager() -> ServerStateManager:
    """Get the singleton instance of the ServerStateManager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = ServerStateManager()
    return _state_manager
