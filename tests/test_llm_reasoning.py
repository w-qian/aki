"""Tests for the LLM reasoning module."""

import unittest

from aki.llm.reasoning import ReasoningConfig, get_reasoning_config
from aki.llm.capabilities import ModelCapability


class TestReasoningConfig(unittest.TestCase):
    """Tests for the ReasoningConfig class."""

    def test_init_default_values(self):
        """Test default initialization values."""
        config = ReasoningConfig()
        self.assertFalse(config.enable)
        self.assertEqual(config.budget_tokens, 4096)

    def test_init_custom_values(self):
        """Test custom initialization values."""
        config = ReasoningConfig(enable=True, budget_tokens=2048)
        self.assertTrue(config.enable)
        self.assertEqual(config.budget_tokens, 2048)

    def test_min_budget_tokens(self):
        """Test that budget_tokens has a minimum value."""
        config = ReasoningConfig(budget_tokens=500)
        self.assertEqual(config.budget_tokens, 1024)  # Should enforce minimum

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = ReasoningConfig(enable=True, budget_tokens=3072)
        config_dict = config.to_dict()
        self.assertEqual(config_dict, {"enable": True, "budget_tokens": 3072})

    def test_from_dict(self):
        """Test creation from dictionary."""
        config_dict = {"enable": True, "budget_tokens": 5120}
        config = ReasoningConfig.from_dict(config_dict)
        self.assertTrue(config.enable)
        self.assertEqual(config.budget_tokens, 5120)

    def test_from_dict_missing_values(self):
        """Test creation from dictionary with missing values."""
        config_dict = {}
        config = ReasoningConfig.from_dict(config_dict)
        self.assertFalse(config.enable)  # Default value
        self.assertEqual(config.budget_tokens, 4096)  # Default value


class TestGetReasoningConfig(unittest.TestCase):
    """Tests for the get_reasoning_config function."""

    def test_default_config(self):
        """Test getting default configuration."""
        config = get_reasoning_config("test-model", set())
        self.assertFalse(config.enable)
        self.assertEqual(config.budget_tokens, 4096)

    def test_with_capability(self):
        """Test with model that has reasoning capability."""
        capabilities = {ModelCapability.EXTENDED_REASONING}
        config = get_reasoning_config("test-model", capabilities)
        self.assertTrue(config.enable)
        self.assertEqual(config.budget_tokens, 4096)

    def test_with_state(self):
        """Test with model that has reasoning capability and state settings."""
        capabilities = {ModelCapability.EXTENDED_REASONING}
        state = {"reasoning_enabled": True, "budget_tokens": 6144}
        config = get_reasoning_config("test-model", capabilities, state)
        self.assertTrue(config.enable)
        self.assertEqual(config.budget_tokens, 6144)

    def test_state_disabled_overrides_capability(self):
        """Test state disabled setting overrides capability."""
        capabilities = {ModelCapability.EXTENDED_REASONING}
        state = {"reasoning_enabled": False, "budget_tokens": 3072}
        config = get_reasoning_config("test-model", capabilities, state)
        self.assertFalse(config.enable)
        self.assertEqual(config.budget_tokens, 3072)


if __name__ == "__main__":
    unittest.main()
