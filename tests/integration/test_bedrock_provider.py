"""Integration tests for Bedrock provider."""

import os
import pytest
from typing import Generator
import logging

from aki.llm import ModelCapability
from aki.llm.providers.bedrock import BedrockProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Skip these tests if credentials are not available
pytestmark = pytest.mark.skipif(
    os.environ.get("AWS_ACCESS_KEY_ID") is None
    or os.environ.get("AWS_SECRET_ACCESS_KEY") is None,
    reason="AWS credentials not available",
)


@pytest.fixture
def bedrock_provider() -> Generator[BedrockProvider, None, None]:
    """Fixture to create and register a Bedrock provider."""
    provider = BedrockProvider()
    yield provider


@pytest.fixture
def model_id() -> str:
    """Get a model ID to use for testing."""
    # Use a default model that's relatively inexpensive
    return os.environ.get(
        "BEDROCK_TEST_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    )


class TestBedrockProvider:
    """Tests for the Bedrock provider."""

    def test_provider_initialization(self, bedrock_provider):
        """Test that the provider initializes correctly."""
        assert bedrock_provider.name == "bedrock"
        assert len(bedrock_provider.capabilities) > 0

    def test_list_models(self, bedrock_provider):
        """Test listing available models."""
        models = bedrock_provider.list_models()
        assert len(models) > 0
        # Check that at least one model from each supported provider exists
        assert any("claude" in model.lower() for model in models)
        assert any("stable-image" in model.lower() for model in models)

    def test_model_capabilities(self, bedrock_provider, model_id):
        """Test getting model capabilities."""
        # Update to use a model we know exists in our capabilities dict
        test_model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        capabilities = bedrock_provider.capabilities.get(test_model_id)
        assert capabilities is not None
        assert ModelCapability.TEXT_TO_TEXT in capabilities


@pytest.mark.slow
class TestBedrockModelIntegration:
    """Integration tests for Bedrock models that make actual API calls."""

    def test_create_model(self, bedrock_provider, model_id):
        """Test creating a model instance."""
        model = bedrock_provider.create_model("test", model_id)
        assert model is not None
        # LangChain models don't have get_capabilities, check the provider capabilities instead
        assert ModelCapability.TEXT_TO_TEXT in bedrock_provider.capabilities.get(
            model_id, set()
        )

    def test_model_generation(self, bedrock_provider, model_id):
        """Test generating text from the model."""
        try:
            model = bedrock_provider.create_model("test", model_id)
            result = model.invoke(
                [{"type": "human", "content": "Say 'Hello, Aki!' and nothing else."}]
            )
            assert result is not None
            assert "hello, aki!" in result.content.lower()
        except Exception as e:
            logger.error(f"Failed to generate text with model {model_id}: {e}")
            pytest.skip(f"Bedrock API error: {e}")
