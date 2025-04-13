import re
from enum import Enum
from typing import List, Optional, Set, NamedTuple

from .parse_strategy import ParseContext, ParseStrategy
from ..capture import Capture


class CaptureType(Enum):
    """Types of Go syntax elements that can be captured."""

    COMMENT = "comment"
    TYPE = "definition.type"
    INTERFACE = "definition.interface"
    STRUCT = "definition.struct"
    PACKAGE = "definition.package"
    IMPORT = "definition.import"
    FUNCTION = "definition.function"
    METHOD = "definition.method"
    MODULE = "definition.module"
    VARIABLE = "definition.variable"
    CONSTANT = "definition.constant"


class ParseResult(NamedTuple):
    """Result of parsing a capture."""

    content: Optional[str]
    processed_signatures: Set[str] = set()


class GoParseStrategy(ParseStrategy):
    """
    Strategy for parsing Go code captures.
    """

    def parse_capture(
        self,
        capture: Capture,
        lines: List[str],
        processed_chunks: Set[str],
        context: ParseContext,
    ) -> Optional[str]:
        """
        Parse a captured node from the Go syntax tree.

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

        # Comments
        if CaptureType.COMMENT in capture_types:
            return self._parse_block_declaration(
                lines, start_row, end_row, processed_chunks
            ).content

        # Package declarations
        if CaptureType.PACKAGE in capture_types or CaptureType.MODULE in capture_types:
            return self._parse_simple_declaration(
                lines, start_row, processed_chunks
            ).content

        # Import declarations
        if CaptureType.IMPORT in capture_types:
            if "(" in lines[start_row]:
                return self._parse_block_declaration(
                    lines, start_row, end_row, processed_chunks
                ).content
            else:
                return self._parse_simple_declaration(
                    lines, start_row, processed_chunks
                ).content

        # Variable declarations
        if CaptureType.VARIABLE in capture_types:
            return self._parse_block_declaration(
                lines, start_row, end_row, processed_chunks
            ).content

        # Constant declarations
        if CaptureType.CONSTANT in capture_types:
            return self._parse_block_declaration(
                lines, start_row, end_row, processed_chunks
            ).content

        # Type definitions
        if (
            CaptureType.TYPE in capture_types
            or CaptureType.INTERFACE in capture_types
            or CaptureType.STRUCT in capture_types
        ):
            return self._parse_type_definition(
                lines, start_row, end_row, processed_chunks
            ).content

        # Function declarations
        if CaptureType.FUNCTION in capture_types:
            return self._parse_function_or_method(
                lines, start_row, end_row, processed_chunks, False
            ).content

        # Method declarations
        if CaptureType.METHOD in capture_types:
            return self._parse_function_or_method(
                lines, start_row, end_row, processed_chunks, True
            ).content

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

    def _get_function_name(self, lines: List[str], start_row: int) -> Optional[str]:
        """
        Extract the function name from a Go function declaration.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the function definition

        Returns:
            Function name or None if not found
        """
        line = lines[start_row]
        # "func funcName(" pattern detection
        match = re.search(r"func\s+([A-Za-z0-9_]+)\s*\(", line)
        if match:
            return match.group(1)
        return None

    def _get_method_with_receiver(
        self, lines: List[str], start_row: int
    ) -> Optional[str]:
        """
        Extract the method name including receiver type from a Go method declaration.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the method definition

        Returns:
            Method name or None if not found
        """
        line = lines[start_row]
        # "func (r ReceiverType) methodName(" pattern detection
        match = re.search(r"func\s+\(([^)]+)\)\s+([A-Za-z0-9_]+)\s*\(", line)
        if match:
            return match.group(2)
        return None

    def _find_closing_token(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        open_token: str,
        close_token: str,
    ) -> int:
        """
        Find the line containing the closing token.

        Args:
            lines: The file content split into lines
            start_row: Starting row to search from
            end_row: Ending row to search to
            open_token: The opening token
            close_token: The closing token to find

        Returns:
            Row index where the closing token is found
        """
        for i in range(start_row, end_row + 1):
            if close_token in lines[i]:
                return i
        return start_row

    def _parse_simple_declaration(
        self, lines: List[str], start_row: int, processed_chunks: Set[str]
    ) -> ParseResult:
        """
        Parse a simple single-line declaration.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the declaration
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the declaration
        """
        declaration = lines[start_row].strip()
        if declaration in processed_chunks:
            return ParseResult(None)
        processed_chunks.add(declaration)
        return ParseResult(declaration)

    def _parse_block_declaration(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        processed_chunks: Set[str],
    ) -> ParseResult:
        """
        Parse a block declaration (like imports with parentheses).

        Args:
            lines: The file content split into lines
            start_row: Starting row of the declaration
            end_row: Ending row of the declaration
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the declaration
        """
        if "(" in lines[start_row]:
            block_end_row = self._find_closing_token(
                lines, start_row, end_row, "(", ")"
            )
        else:
            block_end_row = end_row

        declaration = "\n".join(lines[start_row : block_end_row + 1])
        if declaration in processed_chunks:
            return ParseResult(None)
        processed_chunks.add(declaration)
        return ParseResult(declaration)

    def _parse_function_or_method(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        processed_chunks: Set[str],
        is_method: bool,
    ) -> ParseResult:
        """
        Parse a function or method declaration.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the declaration
            end_row: Ending row of the declaration
            processed_chunks: Set of already processed chunks
            is_method: Whether this is a method (with receiver)

        Returns:
            ParseResult with the declaration
        """
        name_key = "method" if is_method else "func"
        get_name = (
            self._get_method_with_receiver if is_method else self._get_function_name
        )
        name = get_name(lines, start_row)

        if name and f"{name_key}:{name}" in processed_chunks:
            return ParseResult(None)

        signature_end_row = self._find_closing_token(
            lines, start_row, end_row, "{", "{"
        )
        signature = "\n".join(lines[start_row : signature_end_row + 1]).strip()
        clean_signature = signature.split("{")[0].strip()

        if clean_signature in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(clean_signature)
        if name:
            processed_chunks.add(f"{name_key}:{name}")
        return ParseResult(clean_signature)

    def _parse_type_definition(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        processed_chunks: Set[str],
    ) -> ParseResult:
        """
        Parse a type definition.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the definition
            end_row: Ending row of the definition
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the definition
        """
        if "{" in lines[start_row]:
            signature_end_row = self._find_closing_token(
                lines, start_row, end_row, "{", "}"
            )
        else:
            signature_end_row = end_row

        definition = "\n".join(lines[start_row : signature_end_row + 1])
        if definition in processed_chunks:
            return ParseResult(None)
        processed_chunks.add(definition)
        return ParseResult(definition)
