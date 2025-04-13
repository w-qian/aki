import logging
from typing import Optional, Tuple

import tiktoken

from .filesystem_models import FileSystemNode, FileSystemNodeType


async def format_single_file(file_node: FileSystemNode) -> Tuple[str, str]:
    files_content = await file_node.get_content_string()
    tree = "Directory structure:\n└── " + file_node.name
    _generate_token_string(files_content)
    return tree, files_content


async def _get_files_content(node: FileSystemNode) -> str:
    if node.type == FileSystemNodeType.FILE:
        return await node.get_content_string()
    if node.type == FileSystemNodeType.DIRECTORY:
        contents = []
        for child in node.children:
            child_content = await _get_files_content(child)
            contents.append(child_content)
        return "\n".join(contents)
    return ""


def _create_tree_structure(
    node: FileSystemNode, prefix: str = "", is_last: bool = True
) -> str:
    tree = ""

    if node.name:
        current_prefix = "└── " if is_last else "├── "
        name = (
            node.name + "/" if node.type == FileSystemNodeType.DIRECTORY else node.name
        )
        tree += prefix + current_prefix + name + "\n"

    if node.type == FileSystemNodeType.DIRECTORY:
        # Adjust prefix only if we added a node name
        new_prefix = prefix + ("    " if is_last else "│   ") if node.name else prefix
        children = node.children
        for i, child in enumerate(children):
            tree += _create_tree_structure(
                node=child, prefix=new_prefix, is_last=i == len(children) - 1
            )

    return tree


def _generate_token_string(context_string: str) -> Optional[str]:
    try:
        encoding = tiktoken.get_encoding("o200k_base")
        total_tokens = len(encoding.encode(context_string, disallowed_special=()))
        logging.debug(f"Total {total_tokens} tokens")
    except (ValueError, UnicodeEncodeError) as exc:
        print(exc)
        return None

    if total_tokens > 1_000_000:
        return f"{total_tokens / 1_000_000:.1f}M"

    if total_tokens > 1_000:
        return f"{total_tokens / 1_000:.1f}k"

    return str(total_tokens)


async def format_directory(root_node: FileSystemNode) -> Tuple[str, str]:
    tree = "Directory structure:\n" + _create_tree_structure(root_node)
    files_content = await _get_files_content(root_node)

    _generate_token_string(tree + files_content)
    return tree, files_content
