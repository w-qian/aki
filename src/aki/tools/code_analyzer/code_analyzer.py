import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from aki.tools.code_analyzer.repository_reader import read
from aki.tools.file_management.base_tools import ReadFileTool as ReadFileBase


class CodeAnalyzerInput(BaseModel):
    """Input for the package analyzer tool."""

    dir_path: str = Field(description="Path to the directory to analyze")
    include_tree: bool = Field(
        description="Flag to decide whether result includes a hierarchical tree representation of the code structure"
    )
    include_content: bool = Field(
        description="Flag to decide whether result includes actual source code content like method name and annotations"
    )


class CodeAnalyzerTool(ReadFileBase, BaseTool):
    """A tool to analyze package contents using tree-sitter."""

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        logging.warning("Please use async _arun for CodeAnalyzerTool")
        pass

    name: str = "code_analyzer"
    description: str = (
        "Analyzes source code to extract structural information from codebases. The tool performs language-specific "
        "parsing to identify key elements like function signatures, class declarations, and module structures while "
        "filtering out files fit ignored pattern. Output can be customized to include or exclude the visual directory "
        "tree structure and the actual source code content."
    )

    args_schema: type[BaseModel] = CodeAnalyzerInput

    async def _arun(
        self,
        dir_path: str = ".",
        include_tree: bool = True,
        include_content: bool = False,
    ) -> str:
        directory_path = Path(dir_path).resolve()
        logging.debug(f"Analyzing directory: {directory_path}")
        tree, content = await read(path=directory_path)
        result = []
        if include_tree and tree:
            result.append(tree)
        if include_content and content:
            result.append(content)
        return "\n".join(result)


def create_code_analyzer_tool() -> CodeAnalyzerTool:
    """Create and return a package analyzer tool."""
    return CodeAnalyzerTool()
