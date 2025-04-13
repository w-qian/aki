"""Tests for the aki.config module."""

import os
from pathlib import Path
from unittest.mock import patch, mock_open

from aki.config import paths
from aki.config import environment


class TestPaths:
    """Tests for the paths module."""

    @patch("pathlib.Path.mkdir")
    @patch("pathlib.Path.home")
    def test_get_aki_home(self, mock_home, mock_mkdir):
        """Test that get_aki_home returns the correct path and creates directory."""
        # Set up mock
        mock_home_path = Path("/mock/home")
        mock_home.return_value = mock_home_path

        # Call the function
        result = paths.get_aki_home()

        # Check the result is correct
        assert result == mock_home_path / ".aki"

        # Check that mkdir was called with exist_ok=True
        mock_mkdir.assert_called_once_with(exist_ok=True)

    @patch("aki.config.paths.get_aki_home")
    def test_get_env_file(self, mock_get_aki_home):
        """Test that get_env_file returns the correct path."""
        # Set up mock
        mock_aki_home = Path("/mock/home/.aki")
        mock_get_aki_home.return_value = mock_aki_home

        # Call the function
        result = paths.get_env_file()

        # Check the result
        assert result == mock_aki_home / ".env"


class TestEnvironment:
    """Tests for the environment module."""

    @patch("aki.config.paths.get_env_file")
    def test_load_env_variables_file_exists(self, mock_get_env_file):
        """Test loading variables from an existing .env file."""
        # Create a temporary file
        env_content = (
            "AWS_ACCESS_KEY_ID=test_key\nAWS_SECRET_ACCESS_KEY=test_secret\n# Comment\n"
        )

        # Set up mocks
        mock_path = Path("/mock/.aki/.env")
        mock_get_env_file.return_value = mock_path

        # Mock the file exists check and open
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=env_content)),
        ):

            # Call the function
            result = environment.load_env_variables()

            # Check the result
            assert result == {
                "AWS_ACCESS_KEY_ID": "test_key",
                "AWS_SECRET_ACCESS_KEY": "test_secret",
            }

    @patch("aki.config.paths.get_env_file")
    def test_load_env_variables_file_not_exists(self, mock_get_env_file):
        """Test loading variables when .env file doesn't exist."""
        # Set up mocks
        mock_path = Path("/mock/.aki/.env")
        mock_get_env_file.return_value = mock_path

        # Mock the file exists check
        with patch("pathlib.Path.exists", return_value=False):
            # Call the function
            result = environment.load_env_variables()

            # Check the result is an empty dict
            assert result == {}

    @patch("aki.config.environment.load_env_variables")
    def test_get_config_value_from_env(self, mock_load_env):
        """Test getting a value that exists in the environment."""
        # Set a test environment variable
        os.environ["TEST_VAR"] = "test_value"

        # Call the function
        result = environment.get_config_value("TEST_VAR", "default")

        # Check the result
        assert result == "test_value"

        # Environment should be checked first, so load_env_variables should not be called
        mock_load_env.assert_not_called()

        # Clean up
        del os.environ["TEST_VAR"]

    @patch.dict(os.environ, {}, clear=True)
    @patch("aki.config.environment.load_env_variables")
    def test_get_config_value_from_file(self, mock_load_env):
        """Test getting a value from the .env file."""
        # Mock the return value of load_env_variables
        mock_load_env.return_value = {"TEST_VAR": "file_value"}

        # Call the function
        result = environment.get_config_value("TEST_VAR", "default")

        # Check the result
        assert result == "file_value"

        # load_env_variables should be called
        mock_load_env.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    @patch("aki.config.environment.load_env_variables")
    def test_get_config_value_default(self, mock_load_env):
        """Test getting a value that doesn't exist."""
        # Mock the return value of load_env_variables
        mock_load_env.return_value = {}

        # Call the function
        result = environment.get_config_value("TEST_VAR", "default")

        # Check the result is the default
        assert result == "default"

        # load_env_variables should be called
        mock_load_env.assert_called_once()
