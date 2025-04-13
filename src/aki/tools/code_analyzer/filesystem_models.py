""" Define the schema for the filesystem representation. """

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

import chardet
from aki.tools.code_analyzer.constants import MAX_OUTPUT_FILE_CHARACTERS
from aki.tools.code_analyzer.file_compressor import parse_file

SEPARATOR = "=" * 2 + "\n"


class FileSystemNodeType(Enum):
    """Enum representing the type of a file system node (directory or file)."""

    DIRECTORY = auto()
    FILE = auto()


@dataclass
class FileSystemStats:
    """Class for tracking statistics during file system traversal."""

    visited: set[Path] = field(default_factory=set)
    total_files: int = 0
    total_size: int = 0


@dataclass
class FileSystemNode:  # pylint: disable=too-many-instance-attributes
    """
    Class representing a node in the file system (either a file or directory).

    This class has more than the recommended number of attributes because it needs to
    track various properties of files and directories for comprehensive analysis.
    """

    name: str
    type: FileSystemNodeType  # e.g., "directory" or "file"
    path_str: str
    path: Path
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    depth: int = 0
    children: list[FileSystemNode] = field(
        default_factory=list
    )  # Using default_factory instead of empty list

    def sort_children(self) -> None:
        """
        Sort the children nodes of a directory according to a specific order.

        Order of sorting:
        1. README.md first
        2. Regular files (not starting with dot)
        3. Regular directories (not starting with dot)
        All groups are sorted alphanumerically within themselves.
        """
        # Separate files and directories
        files = [
            child for child in self.children if child.type == FileSystemNodeType.FILE
        ]
        directories = [
            child
            for child in self.children
            if child.type == FileSystemNodeType.DIRECTORY
        ]

        # Find README.md
        readme_files = [f for f in files if f.name.lower() == "readme.md"]
        other_files = [f for f in files if f.name.lower() != "readme.md"]

        # Separate hidden and regular files/directories
        regular_files = [f for f in other_files if not f.name.startswith(".")]
        regular_dirs = [d for d in directories if not d.name.startswith(".")]

        # Sort each group alphanumerically
        regular_files.sort(key=lambda x: x.name)
        regular_dirs.sort(key=lambda x: x.name)

        self.children = readme_files + regular_files + regular_dirs

    async def get_content_string(self) -> str:
        """
        Return the content of the node as a string.

        This async method returns the content of the node as a string, including the path and content.

        Returns
        -------
        str
            A string representation of the node's content.
        """
        content = await self.content()
        if not content:
            return ""
        content_repr = [
            SEPARATOR,
            f"File: {str(self.path_str).replace(os.sep, '/')}\n",
            SEPARATOR,
            f"{content}\n\n",
        ]
        return "".join(content_repr)

    async def content(self) -> str:  # pylint: disable=too-many-return-statements
        content, encoding = self.read_content()
        if content and encoding:
            return await parse_file(
                content, encoding, self.path_str, MAX_OUTPUT_FILE_CHARACTERS
            )
        return ""

    def read_content(self):
        try:
            with self.path.open("r", encoding="utf-8") as f:
                return f.read(), "utf-8"

        except UnicodeDecodeError:
            sample_size = min(self.path.stat().st_size, 1024 * 1024)  # Max 1MB sample
            with open(self.path, "rb") as f:
                raw_data = f.read(sample_size)
            result = chardet.detect(raw_data)
            if result.get("encoding") and result.get("confidence", 0) > 0.5:
                detected_encoding = result["encoding"]
                try:
                    with self.path.open("r", encoding=detected_encoding) as f:
                        return f.read(), detected_encoding
                except Exception:
                    return "", None
            return "", None
        except Exception:
            return "", None
