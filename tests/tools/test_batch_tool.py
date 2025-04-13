"""Tests for the BatchTool implementation."""

import json
import pytest
from typing import Dict, Any
from unittest.mock import patch

from langchain.tools import BaseTool

from aki.tools.batch_tool import BatchTool, create_batch_tool, ToolInvocation


class SimpleTestTool(BaseTool):
    """A simple test tool for unit testing."""

    name: str = "test_tool"
    description: str = "A test tool for unit testing."

    def _run(self, arg1: str, arg2: int = 0) -> str:
        return f"Test tool ran with arg1={arg1} and arg2={arg2}"

    async def _arun(self, arg1: str, arg2: int = 0) -> str:
        return self._run(arg1, arg2)


class AsyncOnlyTool(BaseTool):
    """A tool that only has async implementation."""

    name: str = "async_only_tool"
    description: str = "A tool that only has async implementation."

    def _run(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("Only async is supported")

    async def _arun(self, param: str) -> str:
        return f"Async only: {param}"


@pytest.fixture
def test_tools_dict() -> Dict[str, BaseTool]:
    """Create a dictionary of test tools."""
    return {
        "test_tool": SimpleTestTool(),
        "async_only_tool": AsyncOnlyTool(),
    }


def test_create_batch_tool(test_tools_dict: Dict[str, BaseTool]) -> None:
    """Test creating a batch tool instance."""
    batch_tool = create_batch_tool(test_tools_dict)
    assert batch_tool.name == "batch_tool"
    assert batch_tool._tools_dict == test_tools_dict


@pytest.mark.asyncio
async def test_batch_tool_execution(test_tools_dict: Dict[str, BaseTool]) -> None:
    """Test executing multiple tools in batch."""
    batch_tool = BatchTool(tools_dict=test_tools_dict)

    # Create invocations
    invocations = [
        ToolInvocation(
            name="test_tool", arguments=json.dumps({"arg1": "hello", "arg2": 42})
        ),
        ToolInvocation(
            name="async_only_tool", arguments=json.dumps({"param": "world"})
        ),
    ]

    # Execute batch
    result = await batch_tool._arun(invocations=invocations)

    # Verify results
    assert result["test_tool"] == "Test tool ran with arg1=hello and arg2=42"
    assert result["async_only_tool"] == "Async only: world"


@pytest.mark.asyncio
async def test_batch_tool_handles_errors(test_tools_dict: Dict[str, BaseTool]) -> None:
    """Test that the batch tool handles errors gracefully."""
    batch_tool = BatchTool(tools_dict=test_tools_dict)

    # Create invocations with one bad tool
    invocations = [
        ToolInvocation(
            name="test_tool", arguments=json.dumps({"arg1": "hello", "arg2": 42})
        ),
        ToolInvocation(
            name="non_existent_tool", arguments=json.dumps({"param": "world"})
        ),
        ToolInvocation(name="test_tool", arguments="{invalid json}"),
    ]

    # Execute batch
    result = await batch_tool._arun(invocations=invocations)

    # Verify results
    assert result["test_tool"] == "Test tool ran with arg1=hello and arg2=42"
    assert "error" in result["non_existent_tool"]
    assert "Tool 'non_existent_tool' not found" in result["non_existent_tool"]["error"]
    assert "error" in result["test_tool_1"]
    assert "Failed to parse arguments" in result["test_tool_1"]["error"]


@pytest.mark.asyncio
async def test_parameter_conversion(test_tools_dict: Dict[str, BaseTool]) -> None:
    """Test that parameter conversion works for tools that need it."""
    # Mock the parameter conversion function
    with patch("aki.tools.batch_tool.convert_tool_args") as mock_convert:
        # Set up the mock to return a known value
        mock_convert.return_value = {"arg1": "converted", "arg2": 100}

        # Add test_tool to the list of tools needing conversion
        batch_tool = BatchTool(tools_dict=test_tools_dict)
        batch_tool._tools_with_param_conversion = {"test_tool"}

        # Create an invocation that would need conversion
        invocations = [
            ToolInvocation(
                name="test_tool", arguments=json.dumps({"camelCaseArg": "value"})
            ),
        ]

        # Execute batch
        result = await batch_tool._arun(invocations=invocations)

        # Verify conversion was called
        assert mock_convert.call_count > 0
        assert result["test_tool"] == "Test tool ran with arg1=converted and arg2=100"
