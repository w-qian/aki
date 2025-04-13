"""Tests for the tool routing module."""

import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from aki.tools.tool_routing import tool_routing, ToolRegistry


class TestToolRouting(unittest.TestCase):
    """Tests for the tool_routing function."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock tools
        self.mock_tool1 = MagicMock(spec=BaseTool)
        self.mock_tool1.name = "test_tool1"
        self.mock_tool1.invoke.return_value = "Tool 1 result"

        self.mock_tool2 = MagicMock(spec=BaseTool)
        self.mock_tool2.name = "test_tool2"
        self.mock_tool2.invoke.return_value = "Tool 2 result"

        self.tools = [self.mock_tool1, self.mock_tool2]

    def test_empty_state(self):
        """Test with empty state."""
        state = {}
        result = tool_routing(state, self.tools)
        self.assertEqual(result, state)

    def test_no_tools(self):
        """Test with no tools provided."""
        state = {"messages": [AIMessage(content="test")]}
        result = tool_routing(state, [])
        self.assertEqual(result, state)

    def test_no_tool_calls(self):
        """Test with no tool calls in messages."""
        state = {"messages": [AIMessage(content="test")]}
        result = tool_routing(state, self.tools)
        self.assertEqual(result, state)

    def test_tool_call_execution(self):
        """Test successful tool call execution."""
        tool_calls = [{"name": "test_tool1", "args": {"arg1": "value1"}, "id": "call1"}]
        state = {"messages": [AIMessage(content="Using tool", tool_calls=tool_calls)]}

        result = tool_routing(state, self.tools)

        # Check tool was called
        self.mock_tool1.invoke.assert_called_once_with({"arg1": "value1"})

        # Check result message
        self.assertEqual(len(result["messages"]), 1)
        self.assertIsInstance(result["messages"][0], ToolMessage)
        self.assertEqual(result["messages"][0].content, "Tool 1 result")
        self.assertEqual(result["messages"][0].tool_call_id, "call1")
        self.assertEqual(result["messages"][0].name, "test_tool1")

    def test_unknown_tool(self):
        """Test handling of unknown tool."""
        tool_calls = [
            {"name": "unknown_tool", "args": {"arg1": "value1"}, "id": "call1"}
        ]
        state = {
            "messages": [AIMessage(content="Using unknown tool", tool_calls=tool_calls)]
        }

        with patch("aki.tools.tool_routing.logging") as mock_logging:
            result = tool_routing(state, self.tools)

            # Check warning was logged
            mock_logging.warning.assert_called_once()

            # Check error message returned
            self.assertIn("Error", result["messages"][0].content)

    def test_tool_execution_error(self):
        """Test handling of tool execution errors."""
        self.mock_tool1.invoke.side_effect = Exception("Test error")

        tool_calls = [{"name": "test_tool1", "args": {"arg1": "value1"}, "id": "call1"}]
        state = {"messages": [AIMessage(content="Using tool", tool_calls=tool_calls)]}

        with patch("aki.tools.tool_routing.logging") as mock_logging:
            result = tool_routing(state, self.tools)

            # Check error was logged
            mock_logging.error.assert_called_once()

            # Check error message returned
            self.assertIn("Error executing tool", result["messages"][0].content)


class TestToolRegistry(unittest.TestCase):
    """Tests for the ToolRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = ToolRegistry()

        # Create a mock tool
        self.mock_tool = MagicMock(spec=BaseTool)
        self.mock_tool.name = "test_tool"

    def test_register_tool(self):
        """Test registering a tool."""
        self.registry.register_tool(self.mock_tool)
        self.assertEqual(self.registry.get_tool("test_tool"), self.mock_tool)

    def test_register_tool_factory(self):
        """Test registering a tool factory."""
        mock_factory = MagicMock(return_value=self.mock_tool)
        self.registry.register_tool_factory("test_tool", mock_factory)

        # Tool should be created on first access
        tool = self.registry.get_tool("test_tool")
        self.assertEqual(tool, self.mock_tool)
        mock_factory.assert_called_once()

    def test_get_tool_not_found(self):
        """Test getting a tool that doesn't exist."""
        self.assertIsNone(self.registry.get_tool("nonexistent_tool"))

    def test_get_all_tools(self):
        """Test getting all tools."""
        # Register direct tool
        self.registry.register_tool(self.mock_tool)

        # Register factory tool
        mock_tool2 = MagicMock(spec=BaseTool)
        mock_tool2.name = "tool2"
        mock_factory = MagicMock(return_value=mock_tool2)
        self.registry.register_tool_factory("tool2", mock_factory)

        # Get all tools
        tools = self.registry.get_all_tools()

        # Should have both tools
        self.assertEqual(len(tools), 2)
        self.assertIn(self.mock_tool, tools)
        self.assertIn(mock_tool2, tools)


if __name__ == "__main__":
    unittest.main()
