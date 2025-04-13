"""Tests for the Bedrock provider."""

import pytest
from unittest.mock import patch, MagicMock


from aki.llm.capabilities import ModelCapability
from aki.llm.providers.bedrock import (
    BedrockProvider,
    validate_bedrock_access,
    create_session_from_env,
)


class TestBedrockHelperFunctions:
    """Tests for Bedrock helper functions."""

    @patch("boto3.Session")
    @patch("aki.config.environment.get_config_value")
    def test_validate_bedrock_access_success(self, mock_get_config, mock_session):
        """Test validation with successful response."""
        # Set up mocks
        mock_get_config.return_value = "us-west-2"
        mock_client = MagicMock()
        mock_client.list_foundation_models.return_value = {
            "modelSummaries": ["model1", "model2"]
        }
        mock_session_instance = MagicMock()
        mock_session_instance.client.return_value = mock_client
        mock_session.return_value = mock_session_instance

        # Call the function
        result = validate_bedrock_access(mock_session_instance)

        # Check the result
        assert result is True
        mock_client.list_foundation_models.assert_called_once()

    @patch("boto3.Session")
    @patch("aki.config.environment.get_config_value")
    def test_validate_bedrock_access_failure(self, mock_get_config, mock_session):
        """Test validation with an exception."""
        # Set up mocks
        mock_get_config.return_value = "us-west-2"
        mock_client = MagicMock()
        mock_client.list_foundation_models.side_effect = Exception("Test error")
        mock_session_instance = MagicMock()
        mock_session_instance.client.return_value = mock_client
        mock_session.return_value = mock_session_instance

        # Call the function
        result = validate_bedrock_access(mock_session_instance)

        # Check the result
        assert result is False

    def test_create_session_from_env_success(self):
        """Test creating session with valid credentials."""
        # Set up the env vars
        env_vars = {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
        }

        # Mock boto3.Session and validate_bedrock_access
        with (
            patch("boto3.Session") as mock_session,
            patch(
                "aki.llm.providers.bedrock.validate_bedrock_access", return_value=True
            ),
        ):

            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance

            # Call the function
            session, message = create_session_from_env(env_vars)

            # Check the results
            assert session == mock_session_instance
            assert message == "Successfully validated credentials"
            mock_session.assert_called_once_with(
                aws_access_key_id="test_key", aws_secret_access_key="test_secret"
            )

    def test_create_session_from_env_missing_keys(self):
        """Test creating session with missing credentials."""
        # Set up env vars with missing key
        env_vars = {"AWS_ACCESS_KEY_ID": "test_key"}

        # Call the function
        session, message = create_session_from_env(env_vars)

        # Check the results
        assert session is None
        assert message == "Missing required AWS credentials"

    def test_create_session_from_env_validation_failure(self):
        """Test creating session with invalid credentials."""
        # Set up the env vars
        env_vars = {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
        }

        # Mock boto3.Session and validate_bedrock_access
        with (
            patch("boto3.Session") as mock_session,
            patch(
                "aki.llm.providers.bedrock.validate_bedrock_access", return_value=False
            ),
        ):

            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance

            # Call the function
            session, message = create_session_from_env(env_vars)

            # Check the results
            assert session is None
            assert message == "Failed to validate Bedrock access"


class TestBedrockProvider:
    """Tests for the BedrockProvider class."""

    def test_provider_initialization(self):
        """Test that provider initialization creates capabilities."""
        provider = BedrockProvider()
        assert provider._model_capabilities is not None
        assert provider._client is None

    def test_provider_name(self):
        """Test the name property."""
        provider = BedrockProvider()
        assert provider.name == "bedrock"

    def test_capabilities(self):
        """Test the capabilities property."""
        provider = BedrockProvider()
        capabilities = provider.capabilities
        assert isinstance(capabilities, dict)
        assert len(capabilities) > 0
        # Check that at least one model has TEXT_TO_TEXT capability
        assert any(
            ModelCapability.TEXT_TO_TEXT in caps for caps in capabilities.values()
        )

    def test_create_client_from_env_file(self):
        """Test creating client from env file."""
        # Create a more isolated test with complete patching of the environment
        with (
            patch("aki.config.environment.get_config_value") as mock_get_config,
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "aki.llm.providers.bedrock.validate_bedrock_access", return_value=True
            ),
            patch("boto3.Session") as mock_session_class,
        ):

            # Set up config mock
            def config_value_side_effect(key, default=None):
                if key == "AWS_DEFAULT_REGION":
                    return "us-west-2"
                elif key == "AWS_ACCESS_KEY_ID":
                    return "test_key"
                elif key == "AWS_SECRET_ACCESS_KEY":
                    return "test_secret"
                return default

            mock_get_config.side_effect = config_value_side_effect

            # Set up boto3 session mock
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_session.client.return_value = mock_client
            mock_session_class.return_value = mock_session

            # Create provider and call method
            provider = BedrockProvider()
            result = provider._create_client()

            # Check the result
            assert result == mock_client
            # Verify client was created with correct parameters
            mock_session.client.assert_called_once()
            assert mock_session.client.call_args[0][0] == "bedrock-runtime"
            assert mock_session.client.call_args[1]["region_name"] == "us-west-2"

    @patch("aki.config.environment.get_config_value")
    @patch("aki.config.paths.get_env_file")
    @patch("pathlib.Path.exists")
    @patch("boto3.Session")
    @patch("aki.llm.providers.bedrock.validate_bedrock_access")
    def test_create_client_from_profile(
        self,
        mock_validate,
        mock_session,
        mock_exists,
        mock_get_env_file,
        mock_get_config,
    ):
        """Test creating client from aki profile."""
        # Set up mocks
        mock_get_config.return_value = "us-west-2"
        mock_env_path = MagicMock()
        mock_get_env_file.return_value = mock_env_path
        mock_exists.return_value = False  # No .env file
        mock_session_instance = MagicMock()
        mock_client = MagicMock()
        mock_session_instance.client.return_value = mock_client
        mock_session.return_value = mock_session_instance
        mock_validate.return_value = True

        # Create provider and call method
        provider = BedrockProvider()
        result = provider._create_client()

        # Check the result
        assert result == mock_client
        mock_session.assert_called_with(profile_name="aki")
        mock_validate.assert_called_with(mock_session_instance)

    @patch("aki.config.environment.get_config_value")
    @patch("aki.config.paths.get_env_file")
    @patch("pathlib.Path.exists")
    @patch("boto3.Session")
    @patch("aki.llm.providers.bedrock.validate_bedrock_access")
    def test_create_client_failure(
        self,
        mock_validate,
        mock_session,
        mock_exists,
        mock_get_env_file,
        mock_get_config,
    ):
        """Test failure to create a client."""
        # Set up mocks
        mock_get_config.return_value = "us-west-2"
        mock_env_path = MagicMock()
        mock_get_env_file.return_value = mock_env_path
        mock_exists.return_value = False  # No .env file
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_validate.return_value = False  # Validation fails

        # Create provider
        provider = BedrockProvider()

        # Check that an error is raised
        with pytest.raises(ValueError):
            provider._create_client()

    def test_get_client_creates_once(self):
        """Test that _get_client only creates a client once."""
        with patch.object(BedrockProvider, "_create_client") as mock_create:
            mock_client = MagicMock()
            mock_create.return_value = mock_client

            provider = BedrockProvider()
            # First call should create the client
            client1 = provider._get_client()
            # Second call should reuse the same client
            client2 = provider._get_client()

            assert client1 == client2 == mock_client
            mock_create.assert_called_once()

    def test_initialize_model_capabilities(self):
        """Test model capabilities dictionary."""
        provider = BedrockProvider()
        capabilities = provider.capabilities

        # Check the result
        assert isinstance(capabilities, dict)
        assert len(capabilities) > 0

        # Check some specific model capabilities
        # Use a model we know should exist
        claude_37 = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        assert claude_37 in capabilities
        assert ModelCapability.TEXT_TO_TEXT in capabilities[claude_37]
        assert ModelCapability.TOOL_CALLING in capabilities[claude_37]
        assert ModelCapability.EXTENDED_REASONING in capabilities[claude_37]

        # Check another model capability
        stable_image = "stability.stable-image-ultra-v1:0"
        assert stable_image in capabilities
        assert ModelCapability.TEXT_TO_IMAGE in capabilities[stable_image]
        assert ModelCapability.EXTENDED_REASONING in capabilities[claude_37]
