"""Tests for the Aki app module.

Simple tests for the main application functionality.
"""

import unittest
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestApp(unittest.TestCase):
    """Tests for the non-async parts of the app module."""

    @patch("chainlit.cli.chainlit_run")
    def test_main_function(self, mock_chainlit_run):
        """Test that the main function calls chainlit_run."""
        # Import inside the test to avoid early importing of the module
        from aki.app import main

        # Call the main function
        main()

        # Verify chainlit_run was called
        mock_chainlit_run.assert_called_once()


@pytest.mark.asyncio
class TestAsyncFunctions:
    """Tests for the async parts of the app module using pytest-asyncio."""

    @patch("chainlit.Message")
    async def test_on_message_handler(self, mock_message):
        """Test that the message handler correctly processes messages and responds."""
        # Setup mock
        mock_instance = AsyncMock()
        mock_message.return_value = mock_instance

        # Import handler function
        from aki.app import on_message

        # Create a mock message
        test_message = MagicMock()
        test_message.content = "Test message"

        # Call the handler
        await on_message(test_message)

        # Verify Message was created with correct content
        mock_message.assert_called_once()
        mock_message.assert_called_with(content="Received: Test message")

        # Verify send was called
        mock_instance.send.assert_called_once()
