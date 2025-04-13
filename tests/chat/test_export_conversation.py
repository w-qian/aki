"""
Test the export conversation functionality.

This script tests the ConversationExporter class to ensure it correctly exports
conversations in JSON and Markdown formats.
"""

import unittest
import asyncio
from unittest.mock import patch

from aki.chat.export_conversation import ConversationExporter


class TestConversationExporter(unittest.TestCase):
    """Tests for the ConversationExporter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.thread_id = "test_thread_id"
        self.test_state = {
            "chat_profile": "test_profile",
            "messages": [
                {
                    "author": "human",
                    "content": "Hello, how are you?",
                    "created_at": "2025-03-07T16:20:08Z",
                },
                {
                    "author": "ai",
                    "content": "I'm doing well, thank you! How can I help you today?",
                    "created_at": "2025-03-07T16:20:15Z",
                },
                {
                    "author": "tool",
                    "name": "test_tool",
                    "content": "Tool execution result",
                    "created_at": "2025-03-07T16:20:20Z",
                },
            ],
        }

    @patch("aki.chat.export_conversation.json.dumps")
    def test_export_as_json(self, mock_json_dumps):
        """Test JSON export format using state messages."""
        mock_json_dumps.return_value = '{"thread_id": "test_thread_id", "chat_profile": "test_profile", "messages": []}'

        # Create an event loop for this test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                ConversationExporter.export_as_json(self.thread_id, self.test_state)
            )
        finally:
            loop.close()

        # Verify JSON.dumps was called with our conversation data
        mock_json_dumps.assert_called_once()
        args, kwargs = mock_json_dumps.call_args
        self.assertEqual(args[0]["thread_id"], self.thread_id)
        self.assertEqual(args[0]["chat_profile"], "test_profile")
        self.assertEqual(len(args[0]["messages"]), 3)

    @patch("aki.chat.export_conversation.cl.chat_context")
    def test_export_as_markdown(self, mock_chat_context):
        """Test Markdown export format using OpenAI messages."""
        # Set up the mock for chat_context
        mock_chat_context.to_openai.return_value = [
            {"role": "user", "content": "Hello, how are you?"},
            {
                "role": "assistant",
                "content": "I'm doing well, thank you! How can I help you today?",
            },
            {"role": "system", "content": "System message"},
        ]

        # Create an event loop for this test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                ConversationExporter.export_as_markdown(self.thread_id, self.test_state)
            )
        finally:
            loop.close()

        # Verify Markdown format
        self.assertIn("# Aki Conversation -", result)
        self.assertIn("**Profile:** test_profile", result)
        self.assertIn("### User", result)
        self.assertIn("### Assistant", result)
        self.assertIn("### System", result)
        self.assertIn("Hello, how are you?", result)
        self.assertIn("I'm doing well, thank you! How can I help you today?", result)
        self.assertIn("System message", result)


class TestDirectExport(unittest.TestCase):
    """Tests for the direct export functionality."""

    @patch("aki.chat.export_conversation.handle_export")
    def test_handle_direct_export_valid_formats(self, mock_handle_export):
        """Test direct export with valid format parameters."""
        from aki.chat.export_conversation import (
            handle_direct_export,
            ExportFormat,
            ConversationExporter,
        )

        # Test each valid format parameter
        valid_formats = [
            # Short formats
            ("j", ExportFormat.JSON, ConversationExporter.export_as_json),
            ("m", ExportFormat.MARKDOWN, ConversationExporter.export_as_markdown),
            # Long formats
            ("json", ExportFormat.JSON, ConversationExporter.export_as_json),
            (
                "markdown",
                ExportFormat.MARKDOWN,
                ConversationExporter.export_as_markdown,
            ),
            # With whitespace
            (" json ", ExportFormat.JSON, ConversationExporter.export_as_json),
            # Mixed case
            ("JsOn", ExportFormat.JSON, ConversationExporter.export_as_json),
        ]

        # Create an event loop for this test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for format_param, expected_format, expected_function in valid_formats:
                # Reset mock
                mock_handle_export.reset_mock()

                # Test the function
                result = loop.run_until_complete(handle_direct_export(format_param))

                # Assert
                self.assertTrue(result, f"Expected True for format '{format_param}'")
                mock_handle_export.assert_called_once()
                # Check the arguments
                format_arg, func_arg = mock_handle_export.call_args[0]
                self.assertEqual(format_arg, expected_format)
                self.assertEqual(func_arg, expected_function)
        finally:
            loop.close()

    @patch("aki.chat.export_conversation.logger")
    @patch("aki.chat.export_conversation.handle_export")
    def test_handle_direct_export_invalid_formats(
        self, mock_handle_export, mock_logger
    ):
        """Test direct export with invalid format parameters."""
        from aki.chat.export_conversation import handle_direct_export

        # Test invalid format parameters
        invalid_formats = [
            "",
            "invalid",
            "jsonx",
            "md",
            "plain",
            "x",
            "t",
            "text",
            "txt",  # Removed plaintext formats are now invalid
            "@#$%",  # Special characters
            "j" * 1000,  # Very long string
            "🔤json",
        ]  # Unicode characters

        # Create an event loop for this test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for format_param in invalid_formats:
                # Reset mocks
                mock_handle_export.reset_mock()
                mock_logger.reset_mock()

                # Test the function
                result = loop.run_until_complete(handle_direct_export(format_param))

                # Assert
                self.assertFalse(
                    result, f"Expected False for invalid format '{format_param}'"
                )
                mock_handle_export.assert_not_called()
                mock_logger.warning.assert_called_with(
                    f"Invalid export format: {format_param.strip().lower()}"
                )
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
