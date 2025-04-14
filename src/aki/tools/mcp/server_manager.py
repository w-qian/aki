"""MCP server manager implementation."""

import json
import os
import subprocess
import threading
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

from ...config.paths import get_aki_home
from .installation import InstallationManager


class McpServer:
    """Represents a connected MCP server."""

    def __init__(
        self,
        name: str,
        command: str,
        args: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        install_scripts: Optional[List[Dict[str, Any]]] = None,
    ):
        self.name = name
        self.command = command
        self.args = args
        self.cwd = cwd
        self.env = env or {}
        self.install_scripts = install_scripts or []
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

        # Check initialization state
        self.state_file = Path(get_aki_home()) / "mcp_server_state.json"
        self.initialized = self._check_initialization()

        self.installation_manager = InstallationManager(
            name=name, command=command, cwd=cwd, install_scripts=install_scripts or []
        )

    def communicate(self, request: dict) -> dict:
        """Send a request to the server and get the response.

        Args:
            request: The JSON-RPC request to send

        Returns:
            The JSON-RPC response

        Raises:
            ValueError: If the server is not running or communication fails
        """
        if not self.process:
            raise ValueError("Server not running")

        with self._lock:
            try:
                # Write request
                request_str = json.dumps(request) + "\n"
                self.process.stdin.write(request_str)
                self.process.stdin.flush()

                # Read response
                response = self.process.stdout.readline()
                if not response:
                    raise ValueError("Server closed connection")

                try:
                    return json.loads(response)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON response from server: {e}")

            except Exception as e:
                logging.error(f"Communication error with server {self.name}: {e}")
                raise ValueError(f"Failed to communicate with server: {e}")

    def _check_initialization(self) -> bool:
        """Check if the server has been initialized during installation."""
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text())
                return state.get("initialized_servers", {}).get(self.name, False)
            except Exception as e:
                logging.warning(
                    f"Failed to read initialization state for {self.name}: {e}"
                )
        return False

    def _update_initialization_state(self, success: bool) -> None:
        """Update the server initialization state."""
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
            else:
                state = {"initialized_servers": {}}

            state["initialized_servers"][self.name] = success
            self.state_file.write_text(json.dumps(state, indent=2))
            self.initialized = success
        except Exception as e:
            logging.warning(f"Failed to update initialization state: {e}")

    def start(self) -> None:
        """Start the MCP server process."""
        if self.process is not None:
            # Check if process is still running
            if self.process.poll() is None:
                logging.debug(f"MCP server {self.name} is already running")
                return
            else:
                logging.info(f"MCP server {self.name} has stopped, restarting...")
                self.process = None

        # Check installation if not initialized
        if not self.initialized:
            if not self.installation_manager.check_installation():
                logging.warning(
                    f"Server '{self.name}' not installed, attempting installation..."
                )
                try:
                    if not self.installation_manager.install():
                        logging.error(
                            f"Failed to install server '{self.name}'. The application may have limited functionality."
                        )
                        self._update_initialization_state(False)
                        return
                    self._update_initialization_state(True)
                except Exception as e:
                    logging.error(
                        f"Error installing server '{self.name}': {e}. The application may have limited functionality."
                    )
                    self._update_initialization_state(False)
                    return

        # Prepare environment with variable substitution
        env = os.environ.copy()
        logging.info(f"Original env before substitution: {self.env}")
        substituted_env = self._substitute_variables(self.env)
        logging.info(f"Substituted env: {substituted_env}")
        env.update(substituted_env)

        try:
            # Substitute variables in command, args and cwd
            resolved_command = self._substitute_variables(self.command)
            resolved_args = [self._substitute_variables(arg) for arg in self.args]
            resolved_cwd = self._substitute_variables(self.cwd) if self.cwd else None

            # Log detailed server start information
            logging.info(f"Starting MCP server '{self.name}':")
            logging.info(f"  Command: {resolved_command}")
            logging.info(f"  Args: {resolved_args}")
            logging.info(f"  Working Directory: {resolved_cwd}")
            logging.info(
                f"  Environment Variables: {self._substitute_variables(self.env)}"
            )

            # Log full command for easy reproduction
            full_cmd = (
                f"cd {resolved_cwd} && {resolved_command} {' '.join(resolved_args)}"
                if resolved_cwd
                else f"{resolved_command} {' '.join(resolved_args)}"
            )
            logging.info(f"  Full Command: {full_cmd}")

            # Ensure working directory exists
            if resolved_cwd and not os.path.exists(resolved_cwd):
                logging.error(f"Working directory does not exist: {resolved_cwd}")
                raise ValueError(f"Working directory does not exist: {resolved_cwd}")

            self.process = subprocess.Popen(
                [resolved_command] + resolved_args,
                cwd=resolved_cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,  # Line buffered
                universal_newlines=True,  # Text mode
                encoding="utf-8",  # Explicitly set encoding
            )

            # Check if process is still running
            if self.process.poll() is not None:
                stderr_output = self.process.stderr.read()
                logging.error(f"Server '{self.name}' failed to start:")
                logging.error(f"  Exit Code: {self.process.poll()}")
                logging.error(f"  Error Output: {stderr_output}")
                raise ValueError(
                    f"Server '{self.name}' failed to start. stderr: {stderr_output}"
                )

            logging.info(f"MCP server {self.name} started")

            # Test server communication
            try:
                response = self.communicate(
                    {"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1}
                )

                if "error" in response:
                    error = response["error"]
                    error_msg = error.get("message", str(error))
                    logging.warning(
                        f"Server {self.name} list_tools failed: {error_msg}"
                    )
                    return

                result = response.get("result", {})
                tools = result.get("tools", [])
                if isinstance(tools, list):
                    tool_names = [
                        t.get("name", "") for t in tools if isinstance(t, dict)
                    ]
                    if tool_names:
                        logging.info(
                            f"MCP server {self.name} provides tools: {', '.join(tool_names)}"
                        )
                    else:
                        logging.info(f"MCP server {self.name} has no tools")
                else:
                    logging.warning(f"Server {self.name} returned invalid tools format")

            except Exception as e:
                logging.warning(f"Failed to list tools from {self.name}: {e}")

        except Exception as e:
            if self.process:
                self.process.terminate()
                self.process = None
            logging.error(f"Failed to start MCP server {self.name}: {e}")
            raise

    def _substitute_variables(self, value: Any) -> Any:
        """Substitute variables in strings.

        Args:
            value: The value to process

        Returns:
            The processed value with variables substituted
        """
        if isinstance(value, dict):
            logging.info(f"Processing dictionary: {value}")
            return {k: self._substitute_variables(v) for k, v in value.items()}
        elif isinstance(value, list):
            logging.info(f"Processing list: {value}")
            return [self._substitute_variables(v) for v in value]
        elif not isinstance(value, str):
            logging.info(f"Skipping non-string value: {value} of type {type(value)}")
            return value

        logging.info(f"Processing string value: {value}")
        # Replace ${aki_home} with actual path
        aki_home = str(get_aki_home())
        logging.info(f"aki_home resolved to: {aki_home}")

        if "${aki_home}" in value:
            new_value = value.replace("${aki_home}", aki_home)
            logging.info(f"Replaced ${aki_home} in '{value}' -> '{new_value}'")
            value = new_value

        # Handle path separators
        if "/" in value or "\\" in value:
            normalized = os.path.normpath(value)
            logging.info(f"Normalized path '{value}' -> '{normalized}'")
            value = normalized

        return value

    def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process is None:
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=5)
            logging.info(f"Stopped MCP server {self.name}")
        except subprocess.TimeoutExpired:
            self.process.kill()
            logging.warning(f"Killed MCP server {self.name} after timeout")
        except Exception as e:
            logging.error(f"Error stopping MCP server {self.name}: {e}")
        finally:
            self.process = None


class McpServerManager:
    """Manages MCP server connections and configuration."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.servers: Dict[str, McpServer] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load MCP server configuration from file."""
        try:
            with open(self.config_path) as f:
                config = json.load(f)

            for name, server_config in config.get("mcpServers", {}).items():
                if not server_config.get("disabled", False):
                    self.servers[name] = McpServer(
                        name=name,
                        command=server_config["command"],
                        args=server_config.get("args", []),
                        cwd=server_config.get("cwd"),
                        env=server_config.get("env", {}),
                        install_scripts=server_config.get("install_scripts", []),
                    )
                    logging.info(f"Loaded MCP server config for {name}")
        except FileNotFoundError:
            logging.warning(f"MCP config file not found at {self.config_path}")
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in MCP config file {self.config_path}")
        except Exception as e:
            logging.error(f"Error loading MCP config: {e}")

    def start_all(self) -> None:
        """Start all enabled MCP servers."""
        for server in self.servers.values():
            try:
                server.start()
            except Exception as e:
                logging.error(f"Failed to start server {server.name}: {e}")

    def stop_all(self) -> None:
        """Stop all running MCP servers."""
        for server in self.servers.values():
            try:
                server.stop()
            except Exception as e:
                logging.error(f"Failed to stop server {server.name}: {e}")

    def get_server(self, name: str) -> Optional[McpServer]:
        """Get an MCP server by name.

        Args:
            name: Name of the server

        Returns:
            The server instance if found, None otherwise
        """
        return self.servers.get(name)

    def list_servers(self) -> List[str]:
        """Get list of connected server names.

        Returns:
            List of server names
        """
        return list(self.servers.keys())

    def install_server(self, name: str) -> bool:
        """Install a specific MCP server.

        Args:
            name: Name of the server to install

        Returns:
            bool: True if installation succeeded, False otherwise
        """
        server = self.get_server(name)
        if not server:
            logging.error(f"Server '{name}' not found in configuration")
            return False

        return server.install()

    def install_all(self) -> Dict[str, bool]:
        """Install all configured MCP servers.

        Returns:
            Dict[str, bool]: Dictionary mapping server names to installation success status
        """
        results = {}
        for name, server in self.servers.items():
            logging.info(f"Installing server '{name}'...")
            results[name] = server.install()
        return results
