"""MCP toolkit implementation."""

import asyncio
import logging
import json
from typing import List, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from .client import McpClientManager

# Create a logger specific to the MCP toolkit
logger = logging.getLogger("aki.tools.mcp.toolkit")


class McpToolInput(BaseModel):
    """Input for the MCP tool execution."""

    server_name: str = Field(
        description="Name of the MCP server providing the tool. REQUIRED - must be specified for every call."
    )
    tool_name: str = Field(
        description="Name of the tool to execute. REQUIRED - must be specified for every call."
    )
    arguments: dict = Field(
        description="Arguments for the tool execution. MUST be valid JSON object matching tool's expected format. Never include XML tags inside arguments."
    )


class McpToolExecutor(BaseTool):
    """Tool for executing MCP tools."""

    name: str = "mcp_tool"
    description: str = """Execute a tool provided by a connected MCP server.

IMPORTANT FORMAT REQUIREMENTS:
1. Arguments must be pure JSON:
   - Keep JSON arguments clean and separate from XML function call wrapper
   - Never include XML tags inside JSON arguments
   - Validate JSON structure before including in function call

2. Required Fields:
   - server_name: Always required for every call
   - tool_name: Always required for every call
   - arguments: Must match tool's expected format

3. Common Pitfalls to Avoid:
   - Don't mix XML tags in JSON arguments
   - Don't forget required server_name and tool_name
   - Ensure JSON is properly formatted and complete

Example Correct Usage:
{
  "server_name": "memory-server",
  "tool_name": "create_entities",
  "arguments": {
    "entities": [{
      "name": "Test",
      "entityType": "User",
      "observations": ["note"]
    }]
  }
}

Available servers and tools will be listed here when servers are running."""

    args_schema: type[BaseModel] = McpToolInput
    client_manager: McpClientManager = Field(exclude=True)
    _server_tools: Dict[str, List[Dict]] = {}

    def __init__(self, client_manager: McpClientManager):
        super().__init__(client_manager=client_manager)
        self._update_server_tools()

    async def _get_server_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get tools from all servers asynchronously."""
        tools_by_server: Dict[str, List[Dict[str, Any]]] = {}

        # Get tools from each server
        for server_name, client in self.client_manager.clients.items():
            try:
                tools = await client.list_tools()
                tools_by_server[server_name] = tools
                logger.debug(f"Got {len(tools)} tools from {server_name}")
            except Exception as e:
                logger.warning(f"Failed to get tools from {server_name}: {e}")
                tools_by_server[server_name] = []

        return tools_by_server

    def _update_server_tools(self) -> None:
        """Update the list of available tools for each server."""
        tools_desc = ["Execute a tool provided by a connected MCP server."]
        tools_desc.append("\nAvailable servers and tools:")

        # Get tools from all servers
        tools_by_server = asyncio.run(self._get_server_tools())

        # Update description with tools information
        for server_name, tools in tools_by_server.items():
            self._server_tools[server_name] = tools
            if tools:
                tools_desc.append(f"\n- {server_name}:")
                for tool in tools:
                    name = tool.get("name", "")
                    desc = tool.get("description", "No description available")
                    schema = tool.get("input_schema", {})

                    # Add tool name and description
                    tools_desc.append(f"  * {name}: {desc}")

                    # Add formatted schema information
                    tools_desc.append(json.dumps(schema))

                tool_names = [t.get("name", "") for t in tools]
                logger.debug(
                    f"MCP server {server_name} provides tools: {', '.join(tool_names)}"
                )
            else:
                logger.warning(f"No tools found for MCP server {server_name}")
                tools_desc.append(f"\n- {server_name}: Server not responding")

        self.description = "\n".join(tools_desc)

    def _run(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Execute the MCP tool."""
        logger.debug(f"Executing tool {tool_name} on server {server_name}")
        return asyncio.run(self._arun(server_name, tool_name, arguments))

    async def _arun(self, server_name: str, tool_name: str, arguments: dict) -> str:
        """Async version of _run."""
        client = self.client_manager.get_client(server_name)
        if not client:
            raise ValueError(f"MCP client '{server_name}' not found")

        # Call the tool
        return await client.call_tool(tool_name, arguments)


class McpToolkit:
    """Toolkit for MCP functionality."""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(McpToolkit, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: Dict = None, config_path: str = None):
        if not self._initialized:
            logger.debug("Initializing McpToolkit")
            if config is None and config_path is None:
                raise ValueError(
                    "Either config or config_path is required for initialization"
                )
            self.client_manager = McpClientManager(
                config=config, config_path=config_path
            )
            McpToolkit._initialized = True

    @classmethod
    def get_instance(cls, config: Dict = None, config_path: str = None) -> "McpToolkit":
        """Get or create the singleton instance."""
        if not cls._instance:
            if config is None and config_path is None:
                raise ValueError(
                    "Either config or config_path is required for initialization"
                )
            cls._instance = cls(config=config, config_path=config_path)
        return cls._instance

    def get_tools(self) -> List[BaseTool]:
        """Get the list of MCP tools."""
        logger.debug("McpToolkit.get_tools() called")
        tools = [McpToolExecutor(self.client_manager)]
        logger.debug(f"Created {len(tools)} MCP tools")
        return tools
