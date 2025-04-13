import re
from enum import Enum
from typing import List, Optional, Set, NamedTuple

from .parse_strategy import ParseContext, ParseStrategy
from ..capture import Capture


class CaptureType(Enum):
    """Types of TypeScript syntax elements that can be captured."""

    COMMENT = "comment"
    INTERFACE = "definition.interface"
    TYPE = "definition.type"
    ENUM = "definition.enum"
    CLASS = "definition.class"
    IMPORT = "definition.import"
    FUNCTION = "definition.function"
    METHOD = "definition.method"
    PROPERTY = "definition.property"


class ParseResult(NamedTuple):
    """Result of parsing a capture."""

    content: Optional[str]
    processed_signatures: Set[str] = set()


class TypeScriptParseStrategy(ParseStrategy):
    """
    Strategy for parsing TypeScript code captures.
    """

    # Regular expression for finding function names
    FUNCTION_NAME_PATTERN = re.compile(
        r"(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*="
    )

    def parse_capture(
        self,
        capture: Capture,
        lines: List[str],
        processed_chunks: Set[str],
        context: ParseContext,
    ) -> Optional[str]:
        """
        Parse a captured node from the TypeScript syntax tree.

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

        # Function capture
        if CaptureType.FUNCTION in capture_types or CaptureType.METHOD in capture_types:
            return self._parse_function_definition(
                lines, start_row, end_row, processed_chunks
            ).content

        # Class capture
        if CaptureType.CLASS in capture_types:
            return self._parse_class_definition(
                lines, start_row, end_row, processed_chunks
            ).content

        # Type definition or import capture
        if (
            CaptureType.INTERFACE in capture_types
            or CaptureType.TYPE in capture_types
            or CaptureType.ENUM in capture_types
            or CaptureType.IMPORT in capture_types
        ):
            return self._parse_type_or_import(
                lines, start_row, end_row, processed_chunks
            ).content

        # Comment capture
        if CaptureType.COMMENT in capture_types:
            return "\n".join(lines[start_row : end_row + 1]).strip()

        return None

    def _get_function_name(self, lines: List[str], start_row: int) -> Optional[str]:
        """
        Extract the function name from a line.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the function definition

        Returns:
            Function name or None if not found
        """
        line = lines[start_row]
        match = self.FUNCTION_NAME_PATTERN.search(line)
        return match.group(1) if match else None

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

    def _parse_function_definition(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        processed_chunks: Set[str],
    ) -> ParseResult:
        """
        Parse a function definition.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the function definition
            end_row: Ending row of the function definition
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the function definition
        """
        function_name = self._get_function_name(lines, start_row)
        if function_name and f"func:{function_name}" in processed_chunks:
            return ParseResult(None)

        signature_end_row = self._find_signature_end(lines, start_row, end_row)
        selected_lines = lines[start_row : signature_end_row + 1]
        cleaned_signature = self._clean_function_signature(selected_lines)

        if cleaned_signature in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(cleaned_signature)
        if function_name:
            processed_chunks.add(f"func:{function_name}")

        return ParseResult(cleaned_signature)

    def _find_signature_end(
        self, lines: List[str], start_row: int, end_row: int
    ) -> int:
        """
        Find the end of a function signature.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the function definition
            end_row: Maximum ending row to check

        Returns:
            Row index where the signature ends
        """
        for i in range(start_row, end_row + 1):
            line = lines[i].strip()
            if ")" in line and (
                line.endswith("{") or line.endswith("=>") or line.endswith(";")
            ):
                return i
        return start_row

    def _clean_function_signature(self, lines: List[str]) -> str:
        """
        Clean a function signature by removing implementation details.

        Args:
            lines: The function signature lines

        Returns:
            Cleaned function signature
        """
        result = lines.copy()
        last_line_index = len(result) - 1
        last_line = result[last_line_index]

        if last_line:
            if "{" in last_line:
                result[last_line_index] = last_line[: last_line.find("{")].strip()
            elif "=>" in last_line:
                result[last_line_index] = last_line[: last_line.find("=>")].strip()

        return "\n".join(result).strip()

    def _parse_class_definition(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        processed_chunks: Set[str],
    ) -> ParseResult:
        """
        Parse a class definition.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the class definition
            end_row: Ending row of the class definition
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the class definition
        """
        selected_lines = [lines[start_row]]

        if start_row + 1 <= end_row:
            next_line = lines[start_row + 1].strip()
            if "extends" in next_line or "implements" in next_line:
                selected_lines.append(next_line)

        cleaned_lines = [line.replace("{", "").strip() for line in selected_lines]
        definition = "\n".join(cleaned_lines).strip()

        if definition in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(definition)
        return ParseResult(definition)

    def _parse_type_or_import(
        self,
        lines: List[str],
        start_row: int,
        end_row: int,
        processed_chunks: Set[str],
    ) -> ParseResult:
        """
        Parse a type definition or import statement.

        Args:
            lines: The file content split into lines
            start_row: Starting row of the definition
            end_row: Ending row of the definition
            processed_chunks: Set of already processed chunks

        Returns:
            ParseResult with the definition
        """
        selected_lines = lines[start_row : end_row + 1]
        definition = "\n".join(selected_lines).strip()

        if definition in processed_chunks:
            return ParseResult(None)

        processed_chunks.add(definition)
        return ParseResult(definition)
