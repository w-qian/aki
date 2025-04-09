"""Example usage of the Bedrock provider."""

import os
import sys
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from aki.llm import llm_factory
from aki.llm.providers.bedrock import BedrockProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file if present
load_dotenv()


def configure_provider() -> None:
    """Configure the Bedrock provider."""
    # Register the Bedrock provider (if not already registered)
    if "bedrock" not in [provider.name for provider in llm_factory._providers.values()]:
        logger.info("Registering Bedrock provider")
        llm_factory.register_provider("bedrock", BedrockProvider())

    # List available models
    models = llm_factory.list_models()
    logger.info(f"Available models: {', '.join(models)}")


def get_model_config() -> Dict[str, Any]:
    """Get model configuration from environment or use defaults."""
    return {
        "model_id": os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-instant-v1"),
        "temperature": float(os.environ.get("BEDROCK_TEMPERATURE", "0.7")),
        "max_tokens": int(os.environ.get("BEDROCK_MAX_TOKENS", "512")),
    }


def ask_model(query: str) -> None:
    """Ask a question to the model."""
    # Configure provider if not already done
    configure_provider()
    
    # Get model configuration
    config = get_model_config()
    model_id = f"(bedrock){config['model_id']}"
    
    logger.info(f"Using model: {model_id}")
    logger.info(f"Temperature: {config['temperature']}")
    logger.info(f"Max tokens: {config['max_tokens']}")
    
    # Create the model
    try:
        model = llm_factory.create_model(
            "bedrock-test",
            model_id,
            temperature=config['temperature'],
            max_tokens=config['max_tokens'],
        )
        
        # Ask the question
        logger.info(f"Asking: {query}")
        response = model.invoke([{"type": "human", "content": query}])
        
        print("\nResponse:")
        print("-" * 50)
        print(response.content)
        print("-" * 50)
        
    except Exception as e:
        logger.error(f"Error invoking model: {e}")


if __name__ == "__main__":
    # Get the query from command line args or use a default
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Tell me a short joke about programming."
    
    # Ask the model
    ask_model(query)