"""Simplified MCP client implementation."""

import json
import logging
import os
import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, AsyncExitStack
from typing import Dict, List, Optional, Any

from anyio import create_memory_object_stream, create_task_group
from anyio.streams.memory import MemoryObjectReceiveStream
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import JSONRPCMessage

import chainlit as cl
from aki.config.constants import MCP_SERVERS_KEY
from aki.config.paths import get_aki_home
from .installation.manager import InstallationManager

logger = logging.getLogger("aki.tools.mcp")

CONNECTION_TIMEOUT = 10  # seconds


def substitute_variables(value: Any) -> Any:
    """Substitute variables in strings, with support for nested structures.

    Args:
        value: Value to process (string, list, dict, or other)

    Returns:
        Processed value with variables substituted
    """
    # Get aki_home for substitution
    aki_home_str = str(get_aki_home())

    if isinstance(value, dict):
        return {k: substitute_variables(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_variables(v) for v in value]
    elif isinstance(value, str) and "${aki_home}" in value:
        return value.replace("${aki_home}", aki_home_str)
    else:
        return value


@asynccontextmanager
async def read_stream_exception_filer(
    original_read: MemoryObjectReceiveStream[JSONRPCMessage | Exception],
) -> AsyncGenerator[MemoryObjectReceiveStream[JSONRPCMessage], None]:
    """Handle exceptions in the original stream."""
    read_stream_writer, filtered_read = create_memory_object_stream(0)
    task_done = False  # Track if the task is done to avoid cancel issue

    async def filter_task() -> None:
        nonlocal task_done
        try:
            async with original_read:
                async for msg in original_read:
                    if isinstance(msg, Exception):
                        logger.debug(f"Filtered exception in stream: {msg}")
                        continue
                    await read_stream_writer.send(msg)
        finally:
            task_done = True
            await read_stream_writer.aclose()

    async with create_task_group() as tg:
        tg.start_soon(filter_task)
        try:
            yield filtered_read
        finally:
            await filtered_read.aclose()
            # Only cancel if the task is still running
            if not task_done:
                tg.cancel_scope.cancel()


@asynccontextmanager
async def mcp_session(
    params: StdioServerParameters,
) -> AsyncGenerator[ClientSession, None]:
    """Connect to an MCP server with timeout protection."""
    try:
        async with asyncio.timeout(CONNECTION_TIMEOUT):
            async with (
                stdio_client(params) as (read, write),
                read_stream_exception_filer(read) as filtered_read,
                ClientSession(filtered_read, write) as session,
            ):
                await session.initialize()
                yield session
    except asyncio.TimeoutError:
        logger.error(f"MCP connection timed out after {CONNECTION_TIMEOUT}s")
        raise RuntimeError("Connection timeout")
    except FileNotFoundError as e:
        if "package.json" in str(e):
            logger.error("MCP server not installed properly (package.json not found)")
        raise
    except Exception as e:
        logger.debug(f"MCP session error: {str(e)}")
        raise


class McpClient:
    """MCP client for connecting to and communicating with MCP servers."""

    def __init__(
        self,
        name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        check_install_script: Optional[Dict[str, Any]] = None,
        install_scripts: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize MCP client.

        Args:
            name: Server name
            command: Command to run server
            args: Command arguments
            env: Environment variables
            check_install_script: Script to check if server is installed
            install_scripts: Scripts to install server
        """
        self.name = name

        # Store installation info (for potential use in error recovery)
        if check_install_script or install_scripts:
            self.installation_manager = InstallationManager(
                name=name,
                check_install_script=check_install_script,
                install_scripts=install_scripts,
            )

        # Set up environment
        aki_home = get_aki_home()
        aki_home.mkdir(parents=True, exist_ok=True)

        # Prepare environment with defaults and substitutions
        base_env = {
            "PATH": os.environ.get("PATH", ""),
            "NODE_ENV": "development",
            "AKI_HOME": str(aki_home),
        }
        if env:
            base_env.update(substitute_variables(env))

        # Create server parameters with substituted values
        self.server_params = StdioServerParameters(
            command=substitute_variables(command),
            args=substitute_variables(args) or [],
            env=base_env,
        )

    async def get_or_create_client(self) -> ClientSession:
        """Get existing client or create a new one from Chainlit session."""
        # Initialize session storage if needed
        if not hasattr(cl.context.session, "mcp_sessions"):
            cl.context.session.mcp_sessions = {}

        # Use name as key for session lookup
        if self.name in cl.context.session.mcp_sessions:
            client, _ = cl.context.session.mcp_sessions[self.name]
            return client

        # Create a new client with exit stack for clean resource management
        exit_stack = AsyncExitStack()

        try:
            client = await exit_stack.enter_async_context(
                mcp_session(self.server_params)
            )
            cl.context.session.mcp_sessions[self.name] = (client, exit_stack)
            return client
        except Exception as e:
            # Ensure exit stack is cleaned up on error
            await exit_stack.aclose()
            raise RuntimeError(f"Failed to connect to {self.name}: {str(e)}") from e

    @staticmethod
    async def close_all_clients() -> None:
        """Close all client connections in the current session."""
        if not hasattr(cl.context.session, "mcp_sessions"):
            return

        for name, (_, exit_stack) in list(cl.context.session.mcp_sessions.items()):
            try:
                await exit_stack.aclose()
                logger.debug(f"Closed MCP session for {name}")
            except Exception as e:
                logger.error(f"Error closing MCP session for {name}: {e}")

        # Clear the sessions
        cl.context.session.mcp_sessions.clear()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server."""
        # Skip if this server is in skip list
        skip_servers = os.environ.get("SKIP_MCP_SERVERS", "").split(",")
        if self.name in skip_servers:
            return []

        try:
            client = await self.get_or_create_client()
            response = await client.list_tools()

            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in response.tools
            ]
        except Exception as e:
            logger.debug(f"Failed to list tools from {self.name}: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        # Skip if server is in skip list
        skip_servers = os.environ.get("SKIP_MCP_SERVERS", "").split(",")
        if self.name in skip_servers:
            return {"error": f"Server {self.name} is disabled (SKIP_MCP_SERVERS)"}

        try:
            client = await self.get_or_create_client()
            return await client.call_tool(tool_name, arguments)
        except asyncio.TimeoutError:
            return {"error": f"Tool call timed out: {tool_name} on {self.name}"}
        except Exception as e:
            return {"error": f"Failed to call tool {tool_name}: {str(e)}"}


class McpClientManager:
    """Manages MCP client connections."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(McpClientManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, config: Dict = None, config_path: str = None):
        """Initialize the client manager."""
        # Skip if already initialized
        if self.initialized:
            return

        if config is None and config_path is None:
            raise ValueError("Either config or config_path is required")

        self.config = config
        self.config_path = config_path
        self.clients = {}
        self._load_config()
        self.initialized = True

    def _load_config(self) -> None:
        """Load MCP configuration."""
        try:
            # Load from file if config not provided directly
            if self.config is None:
                with open(self.config_path) as f:
                    self.config = json.load(f)

            # Create clients for each server in config
            for name, server_config in self.config.get(MCP_SERVERS_KEY, {}).items():
                if server_config.get("disabled", False):
                    continue

                try:
                    self.clients[name] = McpClient(
                        name=name,
                        command=server_config["command"],
                        args=server_config.get("args", []),
                        env=server_config.get("env", {}),
                        check_install_script=server_config.get("check_install_script"),
                        install_scripts=server_config.get("install_scripts"),
                    )
                except Exception as e:
                    logger.error(f"Failed to create client for {name}: {e}")

        except FileNotFoundError:
            logger.warning(f"MCP config file not found at {self.config_path}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in config file {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading MCP config: {e}")

    async def cleanup_session_clients(self) -> None:
        """Close all open client connections."""
        await McpClient.close_all_clients()

    @classmethod
    def get_instance(
        cls, config: Dict = None, config_path: str = None
    ) -> "McpClientManager":
        """Get or create the singleton instance."""
        if not cls._instance:
            return cls(config=config, config_path=config_path)

        # Handle reconfiguration
        if config is not None or config_path is not None:
            # Store new config info
            cls._instance.config = config or cls._instance.config
            cls._instance.config_path = config_path or cls._instance.config_path

            # Reset clients and reload
            cls._instance.clients = {}
            cls._instance._load_config()

            # Update toolkit descriptions if available
            try:
                from aki.tools.mcp.toolkit import McpToolkit

                toolkit = McpToolkit.get_instance(
                    config=cls._instance.config, config_path=cls._instance.config_path
                )
                tools = toolkit.get_tools()
                if tools:
                    tools[0]._update_server_tools()
            except Exception as e:
                logger.debug(f"Couldn't update tool descriptions: {e}")

        return cls._instance

    def reload_config(self) -> None:
        """Reload config and reinitialize clients."""
        self.clients = {}
        self._load_config()

    def get_client(self, name: str) -> Optional[McpClient]:
        """Get client by name."""
        return self.clients.get(name)

    def list_clients(self) -> List[str]:
        """Get list of available client names."""
        return list(self.clients.keys())
