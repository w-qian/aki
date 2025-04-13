from abc import ABC
from typing import Optional, Dict, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langchain_core.messages import trim_messages

from ..capabilities import ModelCapability
from ..token_counter import tiktoken_counter


class LLMModel(BaseChatModel):
    """Base model with capabilities"""

    def __init__(self, capabilities: set[ModelCapability]):
        self._capabilities = capabilities
        super().__init__()

    def get_capabilities(self) -> set[ModelCapability]:
        """Get the capabilities of this model.

        Returns:
            Set of ModelCapability values supported by this model
        """
        return self._capabilities


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def create_model(
        self, name: str, model: str, tools: Optional[List] = None, **kwargs
    ) -> LLMModel:
        """Create a model instance with the specified configuration.

        Args:
            name: Name for the model instance
            model: Model identifier
            tools: Optional list of tools to provide to the model
            **kwargs: Additional model configuration parameters

        Returns:
            LLMModel: The created model instance
        """
        pass

    def list_models(
        self, capabilities: Optional[set[ModelCapability]] = None
    ) -> List[str]:
        """List available models, optionally filtered by capabilities.

        Args:
            capabilities: Optional set of required capabilities

        Returns:
            List of model identifiers
        """
        pass

    def filter_messages(
        self, messages: List[AnyMessage], max_tokens: int = 100000
    ) -> List[AnyMessage]:
        """Filter messages for compatibility with this provider.

        Args:
            messages: List of messages to filter
            max_tokens: Maximum number of tokens to allow

        Returns:
            List of filtered messages
        """
        # Default implementation: trim messages to max tokens
        return trim_messages(
            messages, max_tokens=max_tokens, token_counter=tiktoken_counter
        )

    @property
    def name(self) -> str:
        """The name of this provider."""
        raise NotImplementedError

    @property
    def capabilities(self) -> Dict[str, set[ModelCapability]]:
        """Map of model names to their capabilities."""
        raise NotImplementedError
