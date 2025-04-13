from enum import Enum
from typing import List, Optional, Set, NamedTuple

from .parse_strategy import ParseContext, ParseStrategy
from ..capture import Capture


class CaptureType(Enum):
    """Types of Python syntax elements that can be captured."""

    COMMENT = "comment"
    CLASS = "definition.class"
    FUNCTION = "definition.function"
    DOCSTRING = "docstring"
    TYPE_ALIAS = "definition.type_alias"


class ParseResult(NamedTuple):
    """Result of parsing a capture."""

    content: Optional[str]
    processed_signatures: Set[str] = set()


class PythonParseStrategy(ParseStrategy):
    """
    Strategy for parsing Python code captures.
    """

    def parse_capture(
        self,
        capture: Capture,
        lines: List[str],
        processed_chunks: Set[str],
        context: ParseContext,
    ) -> Optional[str]:
        """
        Parse a captured node from the Python syntax tree.

        Args:
            capture: The captured syntax node and its name
            lines: The file content split into lines
            processed_chunks: Set of already processed chunks to avoid duplicates
            context: Context information for parsing

        Returns:
            The parsed content or None if it should be skipped
        """
        node = capture.node
        name = capture.name

        if not node or not name:
            return None

        start_row = node.start_point.row
        end_row = node.end_point.row

        if not (0 <= start_row < len(lines)):
            return None

        capture_types = self._get_capture_type(name)

        # Class definition
        if CaptureType.CLASS in capture_types:
            return self._parse_class_definition(
                lines, start_row, processed_chunks
            ).content

        # Function definition
        if CaptureType.FUNCTION in capture_types:
            return self._parse_function_definition(
                lines, start_row, processed_chunks
            ).content

        # Docstring
        if CaptureType.DOCSTRING in capture_types:
            return self._parse_docstring_or_comment(
                lines, start_row, end_row, processed_chunks
            ).content

        # Comment
        if CaptureType.COMMENT in capture_types:
            return self._parse_docstring_or_comment(
                lines, start_row, end_row, processed_chunks
            ).content

        # Type alias
        if CaptureType.TYPE_ALIAS in capture_types:
            return self._parse_type_alias(lines, start_row, processed_chunks).content

        return None

    def _get_capture_type(self, name: str) -> Set[CaptureType]:
        """
        Determine what types of captures are present in the name.

        Args:
            name: The capture name

        Returns:
            Set of capture types found in name
        """
        types = set()
        for capture_type in CaptureType:
            if capture_type.value in name:
                types.add(capture_type)
        return types

    def _get_decorators(self, lines: List[str], start_row: int) -> List[str]:
        """
        Extract decorators above a class or function definition.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the definition

        Returns:
            List of decorator lines
        """
        decorators = []
        current_row = start_row - 1

        while current_row >= 0:
            line = lines[current_row].strip()
            if line.startswith("@"):
                decorators.insert(0, line)  # Add to beginning to maintain order
            else:
                break
            current_row -= 1

        return decorators

    def _get_class_inheritance(self, lines: List[str], start_row: int) -> str:
        """
        Extract the class definition line with inheritance.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the class definition

        Returns:
            Class definition line
        """
        line = lines[start_row]
        match = line.replace(":", "")
        return match

    def _get_function_signature(
        self, lines: List[str], start_row: int
    ) -> Optional[str]:
        """
        Extract the function signature.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the function definition

        Returns:
            Function signature or None if not found
        """
        line = lines[start_row]
        if "def " not in line:
            return None
        return line.replace(":", "")

    def _parse_class_definition(
        self, lines: List[str], start_row: int, processed_chunks: Set[str]
    ) -> ParseResult:
        """
        Parse a class definition.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the class definition
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the class definition
        """
        decorators = self._get_decorators(lines, start_row)
        class_definition = self._get_class_inheritance(lines, start_row)
        full_definition = "\n".join([*decorators, class_definition])

        if full_definition in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(full_definition)
        return ParseResult(full_definition)

    def _parse_function_definition(
        self, lines: List[str], start_row: int, processed_chunks: Set[str]
    ) -> ParseResult:
        """
        Parse a function definition.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the function definition
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the function definition
        """
        decorators = self._get_decorators(lines, start_row)
        signature = self._get_function_signature(lines, start_row)

        if not signature:
            return ParseResult(None)

        full_definition = "\n".join([*decorators, signature])
        if full_definition in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(full_definition)
        return ParseResult(full_definition)

    def _parse_docstring_or_comment(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        processed_chunks: Set[str],
    ) -> ParseResult:
        """
        Parse a docstring or comment.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the docstring/comment
            end_row: Ending row of the docstring/comment
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the docstring/comment
        """
        content = "\n".join(lines[start_row : end_row + 1])

        if content in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(content)
        return ParseResult(content)

    def _parse_type_alias(
        self, lines: List[str], start_row: int, processed_chunks: Set[str]
    ) -> ParseResult:
        """
        Parse a type alias.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the type alias
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the type alias
        """
        type_alias = lines[start_row].strip()

        if type_alias in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(type_alias)
        return ParseResult(type_alias)
