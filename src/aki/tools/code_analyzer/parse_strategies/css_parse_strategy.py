from typing import List, Optional, Set

from .parse_strategy import ParseContext, ParseStrategy
from ..capture import Capture


class CssParseStrategy(ParseStrategy):
    """
    Strategy for parsing CSS code captures.
    """

    def parse_capture(
        self,
        capture: Capture,
        lines: List[str],
        processed_chunks: Set[str],
        context: ParseContext,
    ) -> Optional[str]:
        """
        Parse a captured node from the CSS syntax tree.

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

        # Process CSS-specific capture names
        is_comment_capture = "comment" in name
        is_selector_capture = "selector" in name or "definition.selector" in name
        is_at_rule_capture = "at_rule" in name or "definition.at_rule" in name

        should_select = is_comment_capture or is_selector_capture or is_at_rule_capture

        if not should_select:
            return None

        # Extract all lines for comments, only the first line for others
        if is_comment_capture:
            selected_lines = lines[start_row : end_row + 1]
        else:
            # For selectors and at-rules, extract only the first line
            selected_lines = [lines[start_row]]

        if not selected_lines:
            return None

        chunk = "\n".join(selected_lines)
        normalized_chunk = chunk.strip()

        if normalized_chunk in processed_chunks:
            return None

        processed_chunks.add(normalized_chunk)
        return chunk
