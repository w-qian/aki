import chainlit as cl
from langchain.tools import BaseTool
from typing import Optional
from pydantic import BaseModel, Field


class RenderHtmlInput(BaseModel):
    """Input for rendering HTML content."""

    html_content: Optional[str] = Field(
        None, description="Direct HTML content to render"
    )
    file_path: Optional[str] = Field(None, description="Path to an HTML file to render")


class RenderHtmlTool(BaseTool):
    """Tool for rendering HTML content using Chainlit's HtmlRenderer."""

    name: str = "render_html"
    description: str = """Renders HTML content in the chat UI.
    This tool can either take direct HTML content or a path to an HTML file.
    Use this when you want to display HTML content, such as formatted text, tables, interactive elements, game, or web application.
    """
    args_schema: type[BaseModel] = RenderHtmlInput

    async def _arun(
        self, html_content: Optional[str] = None, file_path: Optional[str] = None
    ) -> str:
        """Run the tool asynchronously."""
        try:
            # Get HTML content from either direct input or file
            content = html_content
            if file_path:
                with open(file_path) as f:
                    content = f.read()
            elif not content:
                raise ValueError("Either html_content or file_path must be provided")

            # Create and send HTML element
            await cl.Message(
                content="",
                elements=[
                    cl.CustomElement(
                        name="HtmlRenderer",
                        props={"html": content},
                        display="inline",
                    )
                ],
            ).send()

            return "HTML content rendered successfully"

        except Exception as e:
            error_msg = f"Error rendering HTML: {str(e)}"
            await cl.Message(error_msg).send()
            return error_msg

    def _run(
        self, html_content: Optional[str] = None, file_path: Optional[str] = None
    ) -> str:
        return self._arun(html_content, file_path)


def create_render_html_tool() -> RenderHtmlTool:
    """Create and return a RenderHtmlTool instance."""
    return RenderHtmlTool()
