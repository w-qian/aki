from typing import Optional, List, Dict, Set
import logging
import requests
from requests.exceptions import ConnectionError, RequestException
import ollama
from langchain_core.language_models import BaseChatModel
from langchain_ollama.chat_models import ChatOllama

from ..capabilities import ModelCapability
from .base import LLMProvider


class OllamaProvider(LLMProvider):
    OLLAMA_API = "http://localhost:11434"

    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            requests.get(f"{self.OLLAMA_API}/api/version", timeout=1)
            return True
        except (ConnectionError, RequestException):
            logging.debug("Ollama service is not available")
            return False

    def create_model(
        self, name: str, model: str, tools: Optional[List] = None, **kwargs
    ) -> BaseChatModel:
        if not self.is_available():
            raise RuntimeError("Ollama service is not available")

        llm = ChatOllama(
            name=name,
            model=model,
            base_url=self.OLLAMA_API,
            temperature=0.2,
        )

        if (
            tools
            and len(tools) > 0
            and ModelCapability.TOOL_CALLING in self.capabilities.get(model, set())
        ):
            llm = llm.bind_tools(tools)
        return llm

    def list_models(self) -> List[str]:
        if not self.is_available():
            logging.debug("Ollama service is not available, returning empty model list")
            return []

        try:
            return [m.model for m in ollama.list().models]
        except Exception as e:
            logging.warning(f"Failed to list Ollama models: {e}")
            return []

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def capabilities(self) -> Dict[str, Set[ModelCapability]]:
        if not self.is_available():
            return {}

        return {
            "deepseek-r1:70b": {
                ModelCapability.TEXT_TO_TEXT,
                ModelCapability.STRUCTURED_OUTPUT,
            },
            "MFDoom/deepseek-r1-tool-calling:70b": {
                ModelCapability.TEXT_TO_TEXT,
                ModelCapability.TOOL_CALLING,
                ModelCapability.STRUCTURED_OUTPUT,
            },
        }
