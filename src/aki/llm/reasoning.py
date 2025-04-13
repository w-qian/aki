"""
Reasoning module for Aki's LLM capabilities.

This module provides support for extended reasoning in compatible LLM providers,
allowing for better handling of complex problems that require structured thinking.
"""

import logging
from typing import Dict, Any, Optional

from .capabilities import ModelCapability

# Default values
DEFAULT_REASONING_ENABLED = False
DEFAULT_BUDGET_TOKENS = 4096  # Default token budget for reasoning


class ReasoningConfig:
    """Configuration class for extended reasoning capabilities."""

    def __init__(
        self,
        enable: bool = DEFAULT_REASONING_ENABLED,
        budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    ):
        """Initialize reasoning configuration.

        Args:
            enable: Whether to enable extended reasoning
            budget_tokens: Token budget for reasoning (min 1024)
        """
        self.enable = enable
        self.budget_tokens = max(1024, budget_tokens)  # Ensure minimum budget

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "enable": self.enable,
            "budget_tokens": self.budget_tokens,
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ReasoningConfig":
        """Create configuration from dictionary."""
        return cls(
            enable=config_dict.get("enable", DEFAULT_REASONING_ENABLED),
            budget_tokens=config_dict.get("budget_tokens", DEFAULT_BUDGET_TOKENS),
        )


def get_reasoning_config(
    model_name: str,
    model_capabilities: set,
    state: Optional[Dict[str, Any]] = None,
) -> ReasoningConfig:
    """Get reasoning configuration based on model capabilities and state.

    Configuration hierarchy (highest to lowest precedence):
    1. Runtime state (UI settings)
    2. Model capability check
    3. Global constants

    Args:
        model_name: Name of the model
        model_capabilities: Set of model capabilities
        state: Optional state dictionary containing model settings

    Returns:
        ReasoningConfig object with the appropriate settings
    """
    config = ReasoningConfig()

    try:
        supports_reasoning = ModelCapability.EXTENDED_REASONING in model_capabilities

        if supports_reasoning and state:
            config.enable = state.get("reasoning_enabled", DEFAULT_REASONING_ENABLED)
            config.budget_tokens = max(
                1024, state.get("budget_tokens", DEFAULT_BUDGET_TOKENS)
            )
        elif supports_reasoning:
            config.enable = True
    except Exception as e:
        logging.warning(f"Error configuring reasoning for {model_name}: {e}")

    logging.debug(f"Final reasoning config for {model_name}: {config.to_dict()}")
    return config
