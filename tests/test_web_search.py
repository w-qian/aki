import unittest
import os
from unittest.mock import patch
from aki.tools.web_search import create_web_search_tool
from langchain_community.tools import DuckDuckGoSearchResults, GoogleSerperResults


class TestWebSearch(unittest.TestCase):
    def test_create_web_search_tool_duckduckgo(self):
        # Test with no SERPER_API_KEY
        with patch.dict(os.environ, {}, clear=True):
            tool = create_web_search_tool()
            self.assertIsInstance(tool, DuckDuckGoSearchResults)
            self.assertEqual(tool.name, "web_search")

    def test_create_web_search_tool_google_serper(self):
        # Test with SERPER_API_KEY
        with patch.dict(
            os.environ, {"SERPER_API_KEY": "fake-api-key-1234567890abcdef"}, clear=True
        ):
            tool = create_web_search_tool()
            self.assertIsInstance(tool, GoogleSerperResults)
            self.assertEqual(tool.name, "web_search")


if __name__ == "__main__":
    unittest.main()
