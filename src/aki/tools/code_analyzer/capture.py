from dataclasses import dataclass

from tree_sitter import Node


@dataclass
class CapturedChunk:
    content: str
    start_row: int
    end_row: int


@dataclass
class Capture:
    name: str
    node: Node
