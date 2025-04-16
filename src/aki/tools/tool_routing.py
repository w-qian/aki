"""
Tool routing and execution management for Aki.

This module provides functionality for routing and executing tool calls from LLMs,
managing tool registration, and handling tool responses.
"""

import logging
from typing import Dict, List, Any, Callable, Optional

from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage
from .think import create_think_tool
from .web_search import create_web_search_tool
from .render_mermaid import create_render_mermaid_tool


def tool_routing(state: Dict[str, Any], tools: List[BaseTool]) -> Dict[str, Any]:
    """
    Route tool calls to appropriate tools and execute them.

    This function processes tool calls from an AI assistant and routes them to
    the appropriate tools for execution, then adds the tool response messages
    to the message history.

    Args:
        state: The current state dictionary containing messages and other state
        tools: List of available tools

    Returns:
        Updated state dictionary with tool responses
    """
    if not tools:
        logging.warning("No tools provided for routing")
        return state

    messages = state.get("messages", [])
    if not messages:
        return state

    # Create tool map for quick lookup
    tool_map = {tool.name: tool for tool in tools}

    # Find the most recent AI message with tool calls
    new_tool_calls = []
    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            new_tool_calls = msg.tool_calls
            break

    if not new_tool_calls:
        return state

    # Track results to add to messages
    results = []

    # Process each tool call
    for tool_call in new_tool_calls:
        tool_name = tool_call.get("name")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id")

        if tool_name not in tool_map:
            logging.warning(f"Tool not found: {tool_name}")
            tool_result = f"Error: Tool '{tool_name}' not found"
        else:
            try:
                tool = tool_map[tool_name]
                logging.debug(f"Executing tool: {tool_name} with args: {tool_args}")
                tool_result = tool.invoke(tool_args)
                logging.debug(f"Tool result: {tool_result}")
            except Exception as e:
                logging.error(f"Error executing tool {tool_name}: {e}")
                tool_result = f"Error executing tool: {e}"

        # Create tool message for result
        results.append(
            ToolMessage(content=str(tool_result), tool_call_id=tool_id, name=tool_name)
        )

    # Add results to messages
    return {"messages": results}


class ToolRegistry:
    """
    Registry for managing available tools.

    This class provides methods for registering, retrieving, and managing tools
    that can be used by AI assistants.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._factories: Dict[str, Callable[[], BaseTool]] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool instance.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool

    def register_tool_factory(self, name: str, factory: Callable[[], BaseTool]) -> None:
        """
        Register a factory function that creates a tool.

        Args:
            name: Name of the tool
            factory: Factory function that creates the tool instance
        """
        self._factories[name] = factory

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name, creating it if necessary.

        Args:
            name: Name of the tool to retrieve

        Returns:
            Tool instance or None if not found
        """
        # Return existing tool if available
        if name in self._tools:
            return self._tools[name]

        # Try to create tool from factory
        if name in self._factories:
            tool = self._factories[name]()
            self._tools[name] = tool
            return tool

        return None

    def get_all_tools(self) -> List[BaseTool]:
        """
        Get all registered tools.

        Returns:
            List of all available tools
        """
        # Create any tools not yet instantiated
        for name, factory in self._factories.items():
            if name not in self._tools:
                self._tools[name] = factory()

        return list(self._tools.values())


# Global tool registry instance
tool_registry = ToolRegistry()
tool_registry.register_tool_factory("think", create_think_tool)
tool_registry.register_tool_factory("web_search", create_web_search_tool)
tool_registry.register_tool_factory("render_mermaid", create_render_mermaid_tool)
