from typing import List, Optional, Set

from .parse_strategy import ParseContext, ParseStrategy
from ..capture import Capture


class DefaultParseStrategy(ParseStrategy):
    """
    Default strategy for parsing captured syntax nodes.
    """

    def parse_capture(
        self,
        capture: Capture,
        lines: List[str],
        processed_chunks: Set[str],
        context: ParseContext,
    ) -> Optional[str]:
        """
        Parse a captured node from the syntax tree using default strategy.

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

        if not 0 <= start_row < len(lines):
            return None

        # Determine if we should select this capture based on its name
        is_name_capture = "name" in name
        is_comment_capture = "comment" in name
        is_import_capture = "import" in name or "require" in name
        should_select = is_name_capture or is_comment_capture or is_import_capture

        if not should_select:
            return None

        # Extract the relevant lines from the file
        selected_lines = lines[start_row : end_row + 1]
        if not selected_lines:
            return None

        chunk = "\n".join(selected_lines)
        normalized_chunk = chunk.strip()

        # Check if we've already processed this chunk
        if normalized_chunk in processed_chunks:
            return None

        processed_chunks.add(normalized_chunk)
        return chunk
