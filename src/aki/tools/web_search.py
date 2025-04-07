from langchain_core.tools import Tool
from langchain_community.tools import DuckDuckGoSearchResults, GoogleSerperResults
import os


# A function that returns a web search tool based on available API keys
def create_web_search_tool() -> Tool:
    """Create and return a web search tool.

    This function checks for available API keys in the environment variables
    and returns an appropriate search tool. If SERPER_API_KEY is available,
    it uses Google Serper API, otherwise falls back to DuckDuckGo.

    Returns:
        Tool: A LangChain Tool object configured for web searching
    """
    # If SERPER_API_KEY exists in environment variables, use GoogleSerperAPIWrapper
    if "SERPER_API_KEY" in os.environ and len(os.environ["SERPER_API_KEY"]) > 15:
        return GoogleSerperResults(
            name="web_search",
            description="Use this when you need to search info from internet.",
        )

    # Otherwise, use DuckDuckGoSearchResults as a fallback
    return DuckDuckGoSearchResults(
        max_results=5,
        output_format="list",
        name="web_search",  # overwrite default tool name
        description="Use this when you need to search info from internet.",
    )
