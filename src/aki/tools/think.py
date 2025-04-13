"""Think Tool for Aki.

This module provides a "think" tool that allows the AI assistant to use a designated 
space for structured thinking during complex tasks, following the implementation 
guidelines from Anthropic's article on improving complex problem-solving abilities.

The tool doesn't retrieve new information or make changes to systems, but provides 
a dedicated space for reasoning and analysis, which improves performance on complex 
tasks requiring policy adherence and multi-step reasoning.
"""

from typing import Optional, Type
from langchain_core.tools import BaseTool, Tool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field


class ThinkInput(BaseModel):
    """Input for the Think tool."""

    thought: str = Field(description="A thought to think about.")


class ThinkTool(BaseTool):
    """Tool for structured thinking without retrieving new information."""

    name: str = "think"
    description: str = (
        "Use the tool to think about something. It will not obtain new information or "
        "change any state, but just append the thought to the log. Use it when complex "
        "reasoning or some cache memory is needed."
    )
    args_schema: Type[BaseModel] = ThinkInput

    def _run(
        self,
        thought: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the think tool with the given thought.

        Args:
            thought: The thought to process
            run_manager: Optional callback manager

        Returns:
            A confirmation message with the thought
        """
        return f"Thought: {thought}"

    async def _arun(
        self,
        thought: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Async execution of the think tool.

        Args:
            thought: The thought to process
            run_manager: Optional callback manager

        Returns:
            A confirmation message with the thought
        """
        return self._run(thought, run_manager=run_manager)


def create_think_tool() -> Tool:
    """Create and return a think tool.

    Returns:
        Tool: A LangChain Tool object configured for structured thinking
    """
    return ThinkTool()
