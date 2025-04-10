"""LLM module for Aki."""

from .factory import LLMFactory
from .capabilities import ModelCapability
from .providers import BedrockProvider
from .providers import OllamaProvider

# Create a default factory instance
llm_factory = LLMFactory()
llm_factory.register_provider("bedrock", BedrockProvider())
llm_factory.register_provider("ollma", OllamaProvider())

__all__ = ["llm_factory", "ModelCapability", "LLMFactory", "BedrockProvider", "OllamaProvider"]
