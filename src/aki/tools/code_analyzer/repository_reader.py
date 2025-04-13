import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Tuple

from .constants import MAX_DIRECTORY_DEPTH, MAX_FILES, MAX_TOTAL_SIZE_BYTES
from .filesystem_models import FileSystemNode, FileSystemNodeType, FileSystemStats
from .ignore_patterns import DEFAULT_IGNORE_PATTERNS
from .output_formatters import format_directory, format_single_file


async def read(path: Path) -> Tuple[str, str]:

    if path.is_file():
        file_node = FileSystemNode(
            name=path.name,
            type=FileSystemNodeType.FILE,
            size=path.stat().st_size,
            file_count=1,
            path_str=str(path.relative_to(path)),
            path=path,
        )
        return await format_single_file(file_node)

    root_node = FileSystemNode(
        name=path.name,
        type=FileSystemNodeType.DIRECTORY,
        path_str=str(path.relative_to(path)),
        path=path,
    )

    stats = FileSystemStats()

    _process_node(
        root_path=path,
        node=root_node,
        stats=stats,
    )

    return await format_directory(root_node)


def _process_node(
    root_path: Path,
    node: FileSystemNode,
    stats: FileSystemStats,
) -> None:
    """
    Process a file or directory item within a directory.

    This function handles each file or directory item, checking if it should be included or excluded based on the
    provided patterns. It handles symlinks, directories, and files accordingly.
    """

    if limit_exceeded(stats, node.depth):
        return

    for sub_path in node.path.iterdir():

        if sub_path in stats.visited:
            continue
        stats.visited.add(sub_path)

        if _should_exclude(path=sub_path, root_path=root_path):
            continue

        if sub_path.is_file():
            _process_file(
                path=sub_path, parent_node=node, stats=stats, root_path=root_path
            )
        elif sub_path.is_dir():
            child_directory_node = FileSystemNode(
                name=sub_path.name,
                type=FileSystemNodeType.DIRECTORY,
                path_str=str(sub_path.relative_to(root_path)),
                path=sub_path,
                depth=node.depth + 1,
            )
            _process_node(
                root_path=root_path,
                node=child_directory_node,
                stats=stats,
            )
            node.children.append(child_directory_node)
            node.size += child_directory_node.size
            node.file_count += child_directory_node.file_count
            node.dir_count += 1 + child_directory_node.dir_count

        else:
            raise ValueError(
                f"Unexpected error: {sub_path} is neither a file nor a directory"
            )

    node.sort_children()


def _process_file(
    path: Path, parent_node: FileSystemNode, stats: FileSystemStats, root_path: Path
) -> None:

    file_size = path.stat().st_size
    if stats.total_size + file_size > MAX_TOTAL_SIZE_BYTES:
        logging.debug(f"Skipping file {path}: would exceed total size limit")
        return

    stats.total_files += 1
    stats.total_size += file_size

    if stats.total_files > MAX_FILES:
        logging.debug(f"Maximum file limit ({MAX_FILES}) reached")
        return

    child = FileSystemNode(
        name=path.name,
        type=FileSystemNodeType.FILE,
        size=file_size,
        file_count=1,
        path_str=str(path.relative_to(root_path)),
        path=path,
        depth=parent_node.depth + 1,
    )

    parent_node.children.append(child)
    parent_node.size += file_size
    parent_node.file_count += 1


def _should_exclude(path: Path, root_path: Path) -> bool:

    rel_str = str(path.relative_to(root_path))
    for pattern in DEFAULT_IGNORE_PATTERNS:
        if pattern and fnmatch(rel_str, pattern):
            return True
    return False


def limit_exceeded(stats: FileSystemStats, depth: int) -> bool:
    if depth > MAX_DIRECTORY_DEPTH:
        logging.debug(f"Maximum depth limit ({MAX_DIRECTORY_DEPTH}) reached")
        return True

    if stats.total_files >= MAX_FILES:
        logging.debug(f"Maximum file limit ({MAX_FILES}) reached")
        return True  # TODO: end recursion

    if stats.total_size >= MAX_TOTAL_SIZE_BYTES:
        logging.debug(
            f"Maxumum total size limit ({MAX_TOTAL_SIZE_BYTES/1024/1024:.1f}MB) reached"
        )
        return True  # TODO: end recursion

    return False
