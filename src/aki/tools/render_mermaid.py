import chainlit as cl
from langchain.tools import BaseTool
from typing import Dict, Any
from pydantic import BaseModel, Field
import asyncio


class RenderMermaidInput(BaseModel):
    """Input for rendering Mermaid diagram content."""

    mermaid_code: str = Field(description="Mermaid diagram code to render")


class RenderMermaidTool(BaseTool):
    """Tool for rendering Mermaid diagrams using a custom renderer."""

    name: str = "render_mermaid"
    description: str = """Renders Mermaid diagram code in the chat UI.
    This tool takes mermaid code as input and renders a pretty diagram with zoom and popup capabilities.
    Use this when you want to visualize diagrams like flowcharts, sequence diagrams, gantt charts, etc.
    If the mermaid code is invalid, the tool will output the syntax error message.
    """
    args_schema: type[BaseModel] = RenderMermaidInput

    async def _arun(self, mermaid_code: str) -> str:
        """Run the tool asynchronously."""
        try:
            if not mermaid_code:
                raise ValueError("Mermaid code must be provided")
            
            # Create and send Mermaid element
            element = cl.CustomElement(
                name="MermaidRenderer",
                props={"mermaidCode": mermaid_code},
                display="inline",
                on_update=on_element_update
            )
            
            await cl.Message(content="", elements=[element]).send()

            return "Mermaid diagram rendered successfully"

        except Exception as e:
            error_msg = f"Error rendering Mermaid diagram: {str(e)}"
            await cl.Message(content=error_msg).send()
            return error_msg

    def _run(self, mermaid_code: str) -> str:
        """Synchronous wrapper for _arun."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._arun(mermaid_code))


def create_render_mermaid_tool() -> RenderMermaidTool:
    """Create and return a RenderMermaidTool instance."""
    return RenderMermaidTool()
