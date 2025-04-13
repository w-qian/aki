from dataclasses import dataclass
from typing import List, Optional, Set, Protocol, Any

from aki.tools.code_analyzer.capture import Capture


@dataclass
class ParseContext:
    """
    Context information for parsing a file.

    Attributes:
        file_content: Content of the file being parsed
        lines: The file content split into lines
        tree: The abstract syntax tree
        query: The query to apply to the tree
        config: Configuration settings
    """

    file_content: str
    lines: List[str]
    tree: Any  # tree_sitter.Tree
    query: Any  # tree_sitter.Query


class ParseStrategy(Protocol):
    """
    Strategy interface for parsing language-specific code structures.
    """

    def parse_capture(
        self,
        capture: Capture,  # { 'node': SyntaxNode, 'name': str }
        lines: List[str],
        processed_chunks: Set[str],
        context: ParseContext,
    ) -> Optional[str]:
        """
        Parse a captured node from the syntax tree.

        Args:
            capture: The captured syntax node and its name
            lines: The file content split into lines
            processed_chunks: Set of already processed chunks to avoid duplicates
            context: Context information for parsing

        Returns:
            The parsed content or None if it should be skipped
        """
        ...
