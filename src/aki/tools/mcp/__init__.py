"""MCP tools package."""

import asyncio
from typing import List, Dict
from langchain.tools import BaseTool
from .toolkit import McpToolkit


async def create_mcp_tools(config: Dict) -> List[BaseTool]:
    """Create MCP tools with the given configuration.

    Args:
        config: MCP configuration dictionary

    Returns:
        List of MCP tools
    """
    # Get or create toolkit singleton instance
    toolkit = McpToolkit.get_instance(config=config)

    # Create and return tools
    return toolkit.get_tools()


def create_mcp_tools_sync(config: Dict) -> List[BaseTool]:
    """Synchronous wrapper for create_mcp_tools.

    Args:
        config: MCP configuration dictionary

    Returns:
        List of MCP tools
    """
    return asyncio.run(create_mcp_tools(config))
