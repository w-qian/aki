from abc import ABC
from typing import Optional, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from ..capabilities import ModelCapability


class LLMModel(BaseChatModel):
    """Base model with capabilities"""

    def __init__(self, capabilities: set[ModelCapability]):
        self._capabilities = capabilities
        super().__init__()

    def get_capabilities(self) -> set[ModelCapability]:
        return self._capabilities


class LLMProvider(ABC):
    def create_model(self, name: str, model: str, **kwargs) -> LLMModel:
        pass

    def list_models(
        self, capabilities: Optional[set[ModelCapability]] = None
    ) -> Dict[str, set[ModelCapability]]:
        pass

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def capabilities(self) -> Dict[str, set[ModelCapability]]:
        raise NotImplementedError
