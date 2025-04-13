"""Tests for the simplified MCP client."""

import os
import pytest
from unittest.mock import patch, AsyncMock

from aki.tools.mcp.client import McpClient, McpClientManager, substitute_variables


def test_substitute_variables():
    """Test variable substitution utility."""
    # Test with string
    result = substitute_variables("path/${aki_home}/config")
    assert "${aki_home}" not in result

    # Test with list
    result = substitute_variables(["normal", "${aki_home}/path"])
    assert all("${aki_home}" not in item for item in result)

    # Test with dict
    result = substitute_variables({"key": "${aki_home}/value", "normal": "value"})
    assert "${aki_home}" not in result["key"]
    assert result["normal"] == "value"


@pytest.mark.asyncio
async def test_mcp_client_initialization():
    """Test MCP client initialization."""
    # Create a client
    client = McpClient(
        name="test-server",
        command="echo",
        args=["test"],
        env={"TEST_VAR": "test_value"},
    )

    # Check that server params are set correctly
    assert client.name == "test-server"
    assert client.server_params.command == "echo"
    assert client.server_params.args == ["test"]
    assert "TEST_VAR" in client.server_params.env
    assert client.server_params.env["TEST_VAR"] == "test_value"


@pytest.mark.asyncio
async def test_client_manager_singleton():
    """Test that the client manager is a singleton."""
    # Create a config
    config = {"mcpServers": {"test": {"command": "echo", "args": ["test"]}}}

    # Create two instances
    manager1 = McpClientManager(config=config)
    manager2 = McpClientManager(config=config)

    # Check they are the same instance
    assert manager1 is manager2

    # Check get_instance
    manager3 = McpClientManager.get_instance(config=config)
    assert manager1 is manager3


@pytest.mark.asyncio
async def test_client_tool_call():
    """Test calling a tool on the client."""
    # Mock the get_or_create_client method
    client = McpClient(name="test-server", command="echo", args=["test"])

    # Mock the client session
    mock_session = AsyncMock()
    mock_session.call_tool.return_value = {"result": "success"}

    # Mock the get_or_create_client method
    with patch.object(
        client, "get_or_create_client", return_value=AsyncMock()
    ) as mock_get:
        mock_get.return_value = mock_session

        # Call a tool
        result = await client.call_tool("test-tool", {"arg": "value"})

        # Check the tool was called
        mock_session.call_tool.assert_called_once_with("test-tool", {"arg": "value"})
        assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_skip_servers():
    """Test skipping servers based on environment variables."""
    # Set the environment variable
    with patch.dict(os.environ, {"SKIP_MCP_SERVERS": "test-server"}):
        client = McpClient(name="test-server", command="echo", args=["test"])

        # Try to list tools
        tools = await client.list_tools()

        # Should be an empty list
        assert tools == []

        # Try to call a tool
        result = await client.call_tool("test-tool", {"arg": "value"})

        # Should return an error
        assert "error" in result
