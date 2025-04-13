import asyncio
import logging
from typing import List, Optional

from .capture import CapturedChunk, Capture
from .language_parser import LanguageParser
from .parse_strategies.parse_strategy import ParseContext
from .supported_lang import SupportedLang

# Singleton instance of the language parser
language_parser_singleton = None


async def parse_file(
    file_content: str, encoding: str, file_path: str, max: int
) -> Optional[str]:
    language_parser = await get_language_parser_singleton()

    # Split the file content into individual lines
    lines = file_content.split("\n")
    if len(lines) < 1:
        return ""
    lang = language_parser.guess_the_lang(file_path)
    if lang is None:
        # Language not supported
        return None
    if lang is SupportedLang.TEXT:
        return file_content[:max]
    query = await language_parser.get_query_for_lang(lang)
    parser = await language_parser.get_parser_for_lang(lang)
    parse_strategy = await language_parser.get_strategy_for_lang(lang)

    processed_chunks = set()
    captured_chunks = []

    try:
        # Parse the file content into an Abstract Syntax Tree (AST)
        tree = parser.parse(file_content.encode(encoding))

        # Create parse context
        context = ParseContext(
            file_content=file_content, lines=lines, tree=tree, query=query
        )

        # Apply the query to the AST and get the captures
        captures = query.captures(tree.root_node)

        # Convert `captures` dictionary into a list of `Capture` objects
        capture_list = [
            Capture(name, node) for name, nodes in captures.items() for node in nodes
        ]

        # Sort captures by their start position
        capture_list.sort(key=lambda cap: cap.node.start_point.row)

        for capture in capture_list:
            captured_chunk_content = parse_strategy.parse_capture(
                capture, lines, processed_chunks, context
            )
            if captured_chunk_content is not None:
                captured_chunks.append(
                    CapturedChunk(
                        content=captured_chunk_content.strip(),
                        start_row=capture.node.start_point.row,
                        end_row=capture.node.end_point.row,
                    )
                )
    except Exception as error:
        logging.error(f"Error parsing file: {error}")

    filtered_chunks = filter_duplicated_chunks(captured_chunks)
    merged_chunks = merge_adjacent_chunks(filtered_chunks)

    return "\n".join([chunk.content for chunk in merged_chunks]).strip()[:max]


def filter_duplicated_chunks(chunks: List[CapturedChunk]) -> List[CapturedChunk]:
    # Group chunks by their start row
    chunks_by_start_row = {}

    for chunk in chunks:
        start_row = chunk.start_row
        if start_row not in chunks_by_start_row:
            chunks_by_start_row[start_row] = []
        chunks_by_start_row[start_row].append(chunk)

    # For each start row, keep the chunk with the most content
    filtered_chunks = []
    for _, row_chunks in chunks_by_start_row.items():
        row_chunks.sort(key=lambda x: len(x.content), reverse=True)
        filtered_chunks.append(row_chunks[0])

    # Sort filtered chunks by start row
    return sorted(filtered_chunks, key=lambda x: x.start_row)


def merge_adjacent_chunks(chunks: List[CapturedChunk]) -> List[CapturedChunk]:
    if len(chunks) <= 1:
        return chunks

    merged = [chunks[0]]

    for i in range(1, len(chunks)):
        current = chunks[i]
        previous = merged[-1]

        # Merge the current chunk with the previous one
        if previous.end_row + 1 == current.start_row:
            previous.content += f"\n{current.content}"
            previous.end_row = current.end_row
        else:
            merged.append(current)

    return merged


_singleton_lock = asyncio.Lock()


async def get_language_parser_singleton():
    global language_parser_singleton
    async with _singleton_lock:
        if not language_parser_singleton:
            language_parser_singleton = LanguageParser()
        return language_parser_singleton
