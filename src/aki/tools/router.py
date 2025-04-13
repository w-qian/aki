from typing import Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class RouterInput(BaseModel):
    """Input for the Router tool."""

    next: str = Field(
        description="Either '__end__' to end the conversation or an available agent name"
    )
    instruction: Optional[str] = Field(
        default=None,
        description="The instruction for the next agent. Required if next is not '__end__'",
    )

    def model_post_init(self, __context) -> None:
        """Validate that instruction is provided when next is not __end__."""
        if self.next != "__end__" and not self.instruction:
            raise ValueError("instruction is required when next is not __end__")


class RouterTool(BaseTool):
    """Tool for routing messages between agents in a multi-agent workflow."""

    name: str = "router"
    description: str = """Route the conversation to another agent or end it.
    Use this when you want to:
    1. Pass the conversation to Akisa with specific instructions
    2. End the conversation when the task is complete
    
    The 'next' parameter must be either '__end__' or an available agent name.
    If routing to Akisa, you must provide instructions."""

    args_schema: type[BaseModel] = RouterInput

    def _run(self, next: str, instruction: Optional[str] = None) -> str:
        """Execute the routing logic.

        Args:
            next: Either '__end__' or an available agent name
            instruction: Instructions for the next agent

        Returns:
            A confirmation message about the routing decision
        """
        if next == "__end__":
            return "Conversation ended."
        else:
            return f"Routing to {next} with instruction: {instruction}"

    async def _arun(self, next: str, instruction: Optional[str] = None) -> str:
        """Async version of _run."""
        return self._run(next, instruction)


def create_router_tool() -> RouterTool:
    """Create and return a RouterTool instance."""
    return RouterTool()
