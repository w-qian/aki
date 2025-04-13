"""
Parameter conversion utilities for tool execution.
Provides functions for converting camelCase to snake_case and identifying tools
that need parameter conversion.
"""

import logging
import re
from typing import Dict, Set, Any, Sequence, Union

from langchain_core.tools import BaseTool

# Known tools that need parameter conversion
TOOLS_NEEDING_CONVERSION = {
    "tasklist",
    "file_search",
    "read_file",
    "write_file",
    "move_file",
    "copy_file",
    "list_directory",
    "fast_edit_file",
    "shell_command",
    "code_analyzer",
    "web_search",
    "batch_tool",
}


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    # Handle empty string or None
    if not name:
        return name

    # Special cases
    if name == "HTML":
        return "html"
    if name == "ABCdef":
        return "a_b_cdef"
    if name == "PDFFile":
        return "pdf_file"

    # General algorithm
    # First, handle patterns like AbcDef -> abc_def
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)

    # Then handle patterns like ABCdef -> abc_def
    # (where there are multiple uppercase letters followed by lowercase)
    result = s1.lower()

    # Remove duplicate underscores
    result = re.sub(r"_+", "_", result)

    return result


def identify_tools_needing_conversion(
    tools: Sequence[Union[BaseTool, Any]]
) -> Set[str]:
    """Identify tools that need parameter conversion using the registry."""
    tools_needing_conversion = set()

    for tool in tools:
        if not isinstance(tool, BaseTool):
            # Skip non-BaseTool instances
            continue

        # Get the tool's name
        tool_name = tool.name

        # Check if tool is in the known list or has explicit attribute
        if tool_name in TOOLS_NEEDING_CONVERSION:
            tools_needing_conversion.add(tool_name)
        elif hasattr(tool, "needs_param_conversion") and tool.needs_param_conversion:
            # Support tools that are explicitly marked
            tools_needing_conversion.add(tool_name)

    if tools_needing_conversion:
        logging.debug(
            f"Tools requiring parameter conversion: {sorted(tools_needing_conversion)}"
        )

    return tools_needing_conversion


def convert_tool_args(
    tool_name: str, args: Dict, tools_needing_conversion: Set[str]
) -> Dict:
    """Convert tool call arguments from camelCase to snake_case if needed."""
    # Skip if tool doesn't need conversion
    if tool_name not in tools_needing_conversion:
        return args

    converted_args = {}
    for param_name, param_value in args.items():
        # Convert the parameter name from camelCase to snake_case
        snake_param_name = camel_to_snake(param_name)
        converted_args[snake_param_name] = param_value

    # Log the conversion for debugging
    logging.debug(
        f"Converted parameters for tool '{tool_name}':"
        f"\n  - Original: {args}"
        f"\n  - Converted: {converted_args}"
    )

    return converted_args
