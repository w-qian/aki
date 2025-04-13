"""Batch Tool for parallel execution of multiple tools in a single request."""

import json
import asyncio
import logging
from typing import Dict, List, Any, ClassVar
from pydantic import BaseModel, Field, ConfigDict

from langchain.tools import BaseTool

from aki.tools.param_conversion import (
    convert_tool_args,
    identify_tools_needing_conversion,
)


class ToolInvocation(BaseModel):
    """Model for a single tool invocation within the batch."""

    name: str = Field(description="Name of the tool to invoke")
    arguments: str = Field(description="JSON string of arguments to pass to the tool")


class BatchToolInput(BaseModel):
    """Input schema for the BatchTool."""

    invocations: List[ToolInvocation] = Field(
        description="List of tool invocations to execute in parallel"
    )


class BatchTool(BaseTool):
    """Tool for executing multiple tool calls in parallel.

    This tool allows the model to make multiple tool calls simultaneously,
    improving response time for operations that would otherwise require
    multiple back-and-forth interactions.
    """

    name: str = "batch_tool"
    description: str = """
    Execute multiple tool calls simultaneously.
    
    Use this tool when you need to invoke multiple tools at once, such as:
    - Fetching multiple pieces of information from different sources
    - Performing related operations on multiple files simultaneously
    - Any scenario where several tool calls can be processed in parallel
    
    This is especially useful for reducing the number of back-and-forth interactions
    when multiple pieces of information are needed at once.
    
    Each invocation must include:
    1. The 'name' of the tool to call
    2. The 'arguments' as a JSON string matching that tool's schema
    
    Example:
    ```json
    {
      "invocations": [
        {
          "name": "read_file",
          "arguments": "{\"file_path\": \"path/to/file.txt\"}"
        },
        {
          "name": "file_search",
          "arguments": "{\"pattern\": \"*.py\", \"dir_path\": \"src\"}"
        }
      ]
    }
    ```
    
    You can combine any available tools in a batch call. Results will be returned with
    the tool name prefix for clarity.
    """

    args_schema: ClassVar[type[BaseModel]] = BatchToolInput

    # This attribute tells the parameter converter to process the tool
    needs_param_conversion: bool = True

    # Configure model with extra fields allowed
    model_config = ConfigDict(extra="allow")

    def __init__(
        self, tools_dict: Dict[str, BaseTool], *args: Any, **kwargs: Any
    ) -> None:
        """Initialize with available tools dictionary.

        Args:
            tools_dict: Dictionary mapping tool names to tool instances
        """
        super().__init__(*args, **kwargs)
        self._tools_dict = tools_dict  # Store as a private attribute
        # Identify tools needing parameter conversion
        self._tools_with_param_conversion = identify_tools_needing_conversion(
            list(tools_dict.values())
        )

        logging.debug(f"BatchTool initialized with {len(tools_dict)} available tools")

    def _parse_arguments(self, tool_name: str, arguments_str: str) -> Dict:
        """Parse and convert arguments for a tool.

        Args:
            tool_name: Name of the tool to invoke
            arguments_str: JSON string of arguments

        Returns:
            Dictionary of parsed and converted arguments
        """
        try:
            # Parse the JSON string
            args = json.loads(arguments_str)

            # Apply parameter conversion if needed
            if tool_name in self._tools_with_param_conversion:
                args = convert_tool_args(
                    tool_name, args, self._tools_with_param_conversion
                )

            return args
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse arguments for {tool_name}: {e}")

    async def _execute_tool(self, tool_name: str, arguments_str: str) -> Any:
        """Execute a single tool asynchronously.

        Args:
            tool_name: Name of the tool to invoke
            arguments_str: JSON string of arguments

        Returns:
            Tool execution result
        """
        if tool_name not in self._tools_dict:
            return {"error": f"Tool '{tool_name}' not found"}

        try:
            # Get the tool and parse arguments
            tool = self._tools_dict[tool_name]
            args = self._parse_arguments(tool_name, arguments_str)

            # Execute the tool
            if hasattr(tool, "_arun"):
                result = await tool._arun(**args)
            else:
                # Fall back to sync execution for tools without async support
                result = tool._run(**args)

            return result
        except Exception as e:
            logging.debug(f"Error executing {tool_name}: {str(e)}", exc_info=True)
            return {"error": f"Tool execution failed: {str(e)}"}

    async def _arun(self, invocations: List[ToolInvocation]) -> str:
        """Execute multiple tool calls in parallel.

        Args:
            invocations: List of tool invocations

        Returns:
            String with newline-separated results from all tools
        """
        if not invocations:
            return "No tool invocations provided"

        # Create tasks for all tool invocations
        tasks = []
        for inv in invocations:
            tasks.append(self._execute_tool(inv.name, inv.arguments))

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks)

        # Format results as a dictionary with numbered keys for duplicate tools
        formatted_results = {}
        tool_counts = {}

        for i, result in enumerate(results):
            tool_name = invocations[i].name

            # Track the number of times this tool has been used
            if tool_name in tool_counts:
                tool_counts[tool_name] += 1
                key = f"{tool_name}_{tool_counts[tool_name]}"
            else:
                tool_counts[tool_name] = 0
                key = tool_name

            # Store result with the appropriate key
            formatted_results[key] = result

        return formatted_results

    def _run(self, invocations: List[ToolInvocation]) -> str:
        """Synchronous execution is not supported."""
        raise NotImplementedError(
            "BatchTool only supports async execution. Use _arun instead."
        )


def create_batch_tool(tools_dict: Dict[str, BaseTool]) -> BatchTool:
    """Create a BatchTool instance with the provided tools dictionary.

    Args:
        tools_dict: Dictionary mapping tool names to tool instances

    Returns:
        BatchTool instance
    """
    return BatchTool(tools_dict=tools_dict)
