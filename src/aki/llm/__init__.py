"""LLM module for Aki."""

from .factory import LLMFactory
from .capabilities import ModelCapability
from .providers import BedrockProvider

# Create a default factory instance
llm_factory = LLMFactory()

__all__ = ["llm_factory", "ModelCapability", "LLMFactory", "BedrockProvider"]
