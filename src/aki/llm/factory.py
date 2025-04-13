from typing import Dict, Optional, List, Set, Tuple
import logging
from langchain_core.language_models.chat_models import BaseChatModel
from .capabilities import ModelCapability
from .providers.base import LLMProvider
from .reasoning import get_reasoning_config, ReasoningConfig


class LLMFactory:
    """Factory for creating and managing LLM instances."""

    # Class-level cache for LLM instances
    _llm_cache: Dict[str, BaseChatModel] = {}

    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}

    def register_provider(self, prefix: str, provider: LLMProvider):
        """Register an LLM provider with the factory.

        Args:
            prefix: Provider prefix used in model names (e.g., 'bedrock')
            provider: LLMProvider instance
        """
        self._providers[prefix] = provider

    def _get_llm_cache_key(
        self,
        model_name: str,
        reasoning_config: Optional[ReasoningConfig] = None,
        temperature: float = 0.6,
        enable_prompt_cache: bool = True,
        **kwargs,
    ) -> str:
        """Generate unique cache key for LLM instance.

        Args:
            model_name: Name of the model
            reasoning_config: Optional reasoning configuration
            temperature: Temperature setting for the model (0.0-1.0)
            enable_prompt_cache: Whether prompt caching is enabled
            kwargs: Additional model parameters that affect caching

        Returns:
            str: Cache key for the LLM instance
        """
        # Round temperature to 1 decimal place for more practical caching
        rounded_temp = round(float(temperature), 1)

        # Build the cache key with model, temperature, and cache setting
        key = f"{model_name}:temp_{rounded_temp}:cache_{enable_prompt_cache}"

        # Add reasoning configuration if enabled
        if reasoning_config and reasoning_config.enable:
            key = f"{key}:reasoning:{reasoning_config.budget_tokens}"

        # Add any other kwargs that would affect model behavior
        for k, v in kwargs.items():
            if k not in ["name", "tools"]:
                key = f"{key}:{k}_{v}"

        return key

    def create_model(
        self, name: str, model: str, tools: Optional[List] = None, **kwargs
    ) -> BaseChatModel:
        """Create an LLM instance with the appropriate provider.

        This method supports caching LLM instances based on their configuration
        to avoid recreating identical models.

        Args:
            name: Name for the model instance
            model: Full model identifier with provider prefix (e.g., '(bedrock)anthropic.claude-3-sonnet-20240229-v1:0')
            tools: Optional list of tools to provide to the model
            **kwargs: Additional parameters for model creation

        Returns:
            BaseChatModel: The created model instance

        Raises:
            ValueError: If no provider is found for the given model
        """
        # Extract provider and model name
        provider_name, model_name, capabilities = self._parse_model_id(model)
        if not provider_name:
            raise ValueError(f"No provider found for model: {model}")

        provider = self._providers[provider_name]

        # Get reasoning configuration
        reasoning_config = get_reasoning_config(
            model_name,
            provider.capabilities.get(model_name, set()),
            kwargs.get("state", None),
        )

        # Apply reasoning settings if enabled
        if reasoning_config.enable:
            kwargs.update(
                {
                    "enable_reasoning": True,
                    "budget_tokens": reasoning_config.budget_tokens,
                }
            )
            logging.debug(
                f"Creating LLM with reasoning enabled, budget_tokens: {reasoning_config.budget_tokens}"
            )

        # Determine if model supports tools
        supports_tools = ModelCapability.TOOL_CALLING in capabilities

        # Get temperature and cache settings
        temperature = float(kwargs.get("temperature", 0.6))
        enable_cache = kwargs.get("enable_prompt_cache", True)

        # Generate cache key and check for cached instance
        cache_key = self._get_llm_cache_key(
            model_name,
            reasoning_config,
            temperature=temperature,
            enable_prompt_cache=enable_cache,
        )

        # Return cached instance if available
        if cache_key in self._llm_cache:
            logging.debug(f"Using cached LLM instance: {cache_key}")
            return self._llm_cache[cache_key]

        # Create model with appropriate parameters
        if supports_tools and tools:
            model_instance = provider.create_model(
                name, model_name, tools=tools, **kwargs
            )
        else:
            if tools is not None and tools != [] and not supports_tools:
                logging.debug(f"Model {model_name} does not support tool calling")
            model_instance = provider.create_model(name, model_name, **kwargs)

        # Cache the new instance
        self._llm_cache[cache_key] = model_instance
        return model_instance

    def _parse_model_id(
        self, model: str
    ) -> Tuple[Optional[str], str, Set[ModelCapability]]:
        """Parse a model identifier into provider, model name, and capabilities.

        Args:
            model: Full model identifier with provider prefix

        Returns:
            Tuple of (provider_name, model_name, capabilities)
        """
        for provider_name, provider in self._providers.items():
            prefix = f"({provider_name})"
            if model.startswith(prefix):
                model_name = model.replace(prefix, "")
                capabilities = provider.capabilities.get(model_name, set())
                return provider_name, model_name, capabilities
        return None, model, set()

    def get_model_capabilities(self, model: str) -> Set[ModelCapability]:
        """Get capabilities for a specific model.

        Args:
            model: Full model identifier with provider prefix

        Returns:
            Set of ModelCapability values supported by the model
        """
        _, _, capabilities = self._parse_model_id(model)
        return capabilities

    def list_models(
        self, capabilities: Optional[set[ModelCapability]] = None
    ) -> List[str]:
        """List available models filtered by capabilities.

        Args:
            capabilities: Optional set of capabilities to filter models by

        Returns:
            List of model identifiers with provider prefixes
        """
        models = []
        for provider in self._providers.values():
            try:
                provider_models = provider.list_models()
                if capabilities:
                    models.extend(
                        [
                            f"({provider.name}){model_name}"
                            for model_name in provider_models
                            if all(
                                cap in provider.capabilities.get(model_name, set())
                                for cap in capabilities
                            )
                        ]
                    )
                else:
                    models.extend(
                        [
                            f"({provider.name}){model_name}"
                            for model_name in provider_models
                        ]
                    )
            except Exception as e:
                logging.warning(
                    f"Failed to list models for provider {provider.name}: {e}"
                )
                continue
        return models

    def clear_cache(self) -> None:
        """Clear the LLM instance cache."""
        self._llm_cache.clear()
        logging.debug("LLM instance cache cleared")
