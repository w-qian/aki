"""Amazon Bedrock provider for Aki."""

import logging
import boto3
from typing import Dict, List, Optional, Set, Any, Tuple
from botocore.client import BaseClient, Config

from langchain_aws import ChatBedrockConverse
from langchain_core.language_models.chat_models import BaseChatModel

from aki.config import get_env_file
from aki.config import get_config_value
from ..capabilities import ModelCapability
from .base import LLMProvider

logger = logging.getLogger(__name__)


def validate_bedrock_access(session: boto3.Session) -> bool:
    """Validate Bedrock access by attempting to list foundation models.

    Args:
        session: boto3.Session to validate

    Returns:
        bool: True if the session has valid Bedrock access, False otherwise
    """
    try:
        # Get region from environment or use default
        region = get_config_value("AWS_DEFAULT_REGION", "us-west-2")
        client = session.client("bedrock", region_name=region)
        response = client.list_foundation_models()
        models = response["modelSummaries"]
        # TODO: need to verify models that we use
        logger.debug(
            f"Successfully validated Bedrock access. Found {len(models)} foundation models."
        )
        return True
    except Exception as e:
        logger.debug(f"Bedrock access validation failed: {str(e)}")
        return False


def create_session_from_env(env_vars: dict) -> Tuple[Optional[boto3.Session], str]:
    """Create a boto3 session from environment variables.

    Args:
        env_vars: Dictionary containing AWS credentials

    Returns:
        Tuple[Optional[boto3.Session], str]: The created session (or None) and a message
    """
    aws_access_key = env_vars.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = env_vars.get("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key or not aws_secret_key:
        return None, "Missing required AWS credentials"

    session = boto3.Session(
        aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key
    )

    if validate_bedrock_access(session):
        return session, "Successfully validated credentials"
    return None, "Failed to validate Bedrock access"


class BedrockProvider(LLMProvider):
    """Provider for Amazon Bedrock models."""

    def __init__(self):
        self._model_capabilities = self.capabilities
        self._logger = logging.getLogger(__name__)
        self._client = None

    def _create_client(self) -> BaseClient:
        """Create a Bedrock client with credential discovery.

        Attempts to create a client using credentials in the following order:
        1. Credentials from ~/.aki/.env file
        2. AWS profile 'aki' (if it exists)

        Returns:
            BaseClient: A configured boto3 bedrock-runtime client
        """
        try:
            # Get region from environment with fallback to default
            region = get_config_value("AWS_DEFAULT_REGION", "us-west-2")
            logger.debug(f"Using AWS region: {region}")
            
            config_obj = Config(
                read_timeout=20000,
                connect_timeout=20000,
                retries={"max_attempts": 5, "mode": "adaptive"},
            )

            # 1. Try loading credentials from ~/.aki/.env
            logger.debug("Attempting to use credentials from ~/.aki/.env")
            env_path = get_env_file()
            if env_path.exists():
                try:
                    # Load credentials from env file
                    env_vars = {
                        "AWS_ACCESS_KEY_ID": get_config_value("AWS_ACCESS_KEY_ID"),
                        "AWS_SECRET_ACCESS_KEY": get_config_value("AWS_SECRET_ACCESS_KEY")
                    }
                    
                    if env_vars["AWS_ACCESS_KEY_ID"] and env_vars["AWS_SECRET_ACCESS_KEY"]:
                        session = boto3.Session(
                            aws_access_key_id=env_vars["AWS_ACCESS_KEY_ID"],
                            aws_secret_access_key=env_vars["AWS_SECRET_ACCESS_KEY"]
                        )
                        
                        if validate_bedrock_access(session):
                            logger.debug("Successfully validated credentials from ~/.aki/.env")
                            return session.client(
                                "bedrock-runtime", region_name=region, config=config_obj
                            )
                        logger.debug("Failed to validate credentials from ~/.aki/.env")
                except Exception as e:
                    logger.warning(f"Error using credentials from ~/.aki/.env: {e}")
            else:
                logger.debug("No ~/.aki/.env file found")

            # 2. Try profile-based authentication
            logger.debug("Attempting to use aki profile authentication")
            try:
                session = boto3.Session(profile_name="aki")
                if validate_bedrock_access(session):
                    logger.debug("Successfully validated aki profile credentials")
                    return session.client(
                        "bedrock-runtime", region_name=region, config=config_obj
                    )
                logger.debug("Failed to validate aki profile credentials")
            except Exception as e:
                logger.debug(f"Error using aki profile: {e}")

            # If we get here, neither method worked
            raise ValueError(
                "Failed to create Bedrock client. Could not find valid credentials in:\n"
                "1. ~/.aki/.env file\n"
                "2. AWS profile 'aki'\n"
            )

        except Exception as e:
            self._logger.error(f"Failed to create Bedrock client: {e}")
            raise

    def _get_client(self) -> BaseClient:
        """Get or create a Bedrock client."""
        if not self._client:
            self._client = self._create_client()
        return self._client

    def _get_model_config(
        self, model: str, tools: Optional[List] = None, **kwargs
    ) -> Dict[str, Any]:
        """Get configuration for a specific model.

        This is a protected method that can be overridden by subclasses
        to implement custom model configuration logic.

        Args:
            model: The model ID
            tools: Optional list of tools for tool-calling models
            **kwargs: Additional model configuration parameters

        Returns:
            Dict[str, Any]: Model configuration dictionary
        """
        # Extract extended reasoning settings if present
        enable_reasoning = kwargs.pop("enable_reasoning", False)
        budget_tokens = kwargs.pop("budget_tokens", 1024)

        # Base model configuration
        model_kwargs = {
            "model": model,
            "max_tokens": kwargs.pop("max_tokens", 8192),
            "temperature": kwargs.pop("temperature", 0.6),
        }

        # Add extended reasoning configuration if enabled for supported models
        if (
            enable_reasoning
            and ModelCapability.EXTENDED_REASONING
            in self._model_capabilities.get(model, set())
        ):
            self._logger.debug(
                f"Enabling extended reasoning for {model} with budget {budget_tokens}"
            )
            # Claude 3.7 requires temperature=1.0 for extended reasoning
            model_kwargs["temperature"] = 1.0
            # Increase max_tokens to accommodate reasoning budget plus regular response
            model_kwargs["max_tokens"] = budget_tokens + model_kwargs.get(
                "max_tokens", 8192
            )
            # Add reasoning configuration to model_kwargs
            model_kwargs["additional_model_request_fields"] = {
                "thinking": {"type": "enabled", "budget_tokens": budget_tokens},
                "anthropic_beta": ["token-efficient-tools-2025-02-19"],
            }

        # Add any remaining kwargs
        for key, value in kwargs.items():
            model_kwargs[key] = value

        return model_kwargs

    def create_model(
        self, name: str, model: str, tools: Optional[List] = None, **kwargs
    ) -> BaseChatModel:
        """Create a new Bedrock chat model.

        Args:
            name: A name for the model instance
            model: The Bedrock model ID
            tools: Optional list of tools for tool-calling models
            **kwargs: Additional arguments to pass to the model

        Returns:
            A configured ChatBedrockConverse instance
        """
        client = self._get_client()
        model_kwargs = self._get_model_config(model, tools, **kwargs)
        model_kwargs["client"] = client

        try:
            llm = ChatBedrockConverse(name=name, **model_kwargs)

            # Add tools if provided and supported
            if (
                tools
                and len(tools) > 0
                and ModelCapability.TOOL_CALLING
                in self._model_capabilities.get(model, set())
            ):
                llm = llm.bind_tools(tools)

            return llm
        except Exception as e:
            self._logger.error(f"Failed to create Bedrock model {model}: {e}")
            raise

    def list_models(self) -> List[str]:
        """List all available models from this provider.

        Returns:
            List of model IDs that can be used with this provider
        """
        return list(self._model_capabilities.keys())

    @property
    def name(self) -> str:
        """Get the name of this provider."""
        return "bedrock"

    @property
    def capabilities(self) -> Dict[str, Set[ModelCapability]]:
        return {
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0": {
                ModelCapability.TEXT_TO_TEXT,
                ModelCapability.IMAGE_TO_TEXT,
                ModelCapability.TOOL_CALLING,
                ModelCapability.STRUCTURED_OUTPUT,
                ModelCapability.EXTENDED_REASONING,
            },
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0": {
                ModelCapability.TEXT_TO_TEXT,
                ModelCapability.IMAGE_TO_TEXT,
                ModelCapability.TOOL_CALLING,
                ModelCapability.STRUCTURED_OUTPUT,
            },
            "us.anthropic.claude-3-5-haiku-20241022-v1:0": {
                ModelCapability.TEXT_TO_TEXT,
                ModelCapability.IMAGE_TO_TEXT,
                ModelCapability.TOOL_CALLING,
                ModelCapability.STRUCTURED_OUTPUT,
            },
            "us.anthropic.claude-3-5-sonnet-20240620-v1:0": {
                ModelCapability.TEXT_TO_TEXT,
                ModelCapability.IMAGE_TO_TEXT,
                ModelCapability.TOOL_CALLING,
                ModelCapability.STRUCTURED_OUTPUT,
            },
            "stability.stable-image-ultra-v1:0": {ModelCapability.TEXT_TO_IMAGE},
            "stability.stable-image-core-v1:0": {ModelCapability.TEXT_TO_IMAGE},
            "us.deepseek.r1-v1:0": {ModelCapability.TEXT_TO_TEXT},
        }
