"""Test cases for the think tool."""

import pytest
from aki.tools.think import create_think_tool, ThinkTool


def test_think_tool_creation():
    """Test that the think tool is created correctly."""
    tool = create_think_tool()
    assert tool.name == "think"
    assert "complex reasoning" in tool.description


def test_think_tool_execution():
    """Test that the think tool executes and returns expected output."""
    tool = ThinkTool()
    thought = "I need to analyze this problem step by step."
    result = tool._run(thought=thought)
    assert result == f"Thought: {thought}"


@pytest.mark.asyncio
async def test_think_tool_async_execution():
    """Test that the think tool executes asynchronously."""
    tool = ThinkTool()
    thought = "Let me consider multiple approaches."
    result = await tool._arun(thought=thought)
    assert result == f"Thought: {thought}"
