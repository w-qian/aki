"""LLM module for Aki."""

# Import capabilities first since they are used by other modules
from .capabilities import ModelCapability

# Then import provider base classes
from .providers.base import LLMProvider, LLMModel

# Then import concrete provider implementations
from .providers.bedrock import BedrockProvider
from .providers.ollama import OllamaProvider

# Finally import and initialize factory
from .factory import LLMFactory

# Create a default factory instance
llm_factory = LLMFactory()
llm_factory.register_provider("bedrock", BedrockProvider())
llm_factory.register_provider("ollama", OllamaProvider())

__all__ = [
    "llm_factory",
    "ModelCapability",
    "LLMFactory",
    "LLMProvider",
    "LLMModel",
    "BedrockProvider",
    "OllamaProvider",
]
