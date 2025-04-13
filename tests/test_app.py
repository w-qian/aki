"""Tests for the Aki app module.

Simple tests for the main application functionality.
"""

import unittest
from unittest.mock import patch


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
