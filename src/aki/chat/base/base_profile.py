"""Base class for all chat profiles."""

import base64
import logging
import chainlit as cl
from typing import TypedDict, Annotated, Dict, Optional
from langchain_core.messages import HumanMessage
from abc import ABC, abstractmethod
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages


class BaseState(TypedDict):
    # Message history
    messages: Annotated[list, add_messages]
    # Name of the chat profile
    chat_profile: str


class BaseProfile(ABC):
    @abstractmethod
    def create_graph(self) -> StateGraph:
        """Define the state graph of the chat profile."""

    @abstractmethod
    def create_default_state(self) -> Dict[str, any]:
        """Define the default state of the chat profile."""

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Get the name of the chat profile."""
        pass

    @property
    def output_chat_model(self) -> str:
        """The name of the chat model to display in the UI."""
        return "default"

    @classmethod
    @abstractmethod
    def chat_profile(cls) -> cl.ChatProfile:
        """Chat profile configuration for the UI."""

    @property
    @abstractmethod
    def chat_settings(self) -> cl.ChatSettings:
        """Chat settings configuration for the UI."""

    def tool_routing(self, state: BaseState):
        """Route to tools node if the last message has tool calls."""
        if isinstance(state, list):
            ai_message = state[-1]
        elif messages := state.get("messages", []):
            ai_message = messages[-1]
        else:
            raise ValueError(f"No messages found in input state to tool_edge: {state}")

        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return END

    async def get_chat_settings(
        self, state: Optional[BaseState] = None
    ) -> cl.ChatSettings:
        """Get the chat settings, optionally resuming from previous state."""
        settings = self.chat_settings

        # Resume settings from previous session
        if state is not None:
            for widget in settings.inputs:
                if widget.id in state:
                    if isinstance(widget, cl.input_widget.Select):
                        if widget.items:
                            if state[widget.id] in widget.items.values():
                                widget.initial = state[widget.id]
                        elif widget.values:
                            if state[widget.id] in widget.values:
                                widget.initial = state[widget.id]
                    elif isinstance(widget, cl.input_widget.Switch):
                        widget.initial = state[widget.id]
                    elif isinstance(widget, cl.input_widget.Slider):
                        if widget.min > state[widget.id]:
                            widget.initial = widget.min
                        elif widget.max < state[widget.id]:
                            widget.initial = widget.max
                        else:
                            widget.initial = state[widget.id]
                    elif isinstance(widget, cl.input_widget.TextInput):
                        widget.initial = state[widget.id]
                    elif isinstance(widget, cl.input_widget.NumberInput):
                        widget.initial = state[widget.id]
                    elif isinstance(widget, cl.input_widget.Tags):
                        if widget.values:
                            widget.initial = [
                                tag for tag in state[widget.id] if tag in widget.values
                            ]
                        else:
                            widget.initial = state[widget.id]
        return await settings.send()

    def format_message(self, msg: cl.Message) -> HumanMessage:
        """Format chainlit message to LangChain message with multimodal support.

        Processes both images and other file types:
        - Images are converted to base64 and included as image URLs
        - Other files (PDFs, Excel, etc.) are converted to text using the read_file tool
          and prepended to the message content
        """
        if not msg.elements:
            return HumanMessage(content=msg.content)

        user_content = msg.content or ""
        document_contents = []

        # Process images separately for multimodal content
        images = [file for file in msg.elements if "image" in file.mime]
        other_files = [file for file in msg.elements if "image" not in file.mime]

        # Process non-image files using read_file with conversion
        if other_files:
            try:
                from aki.tools.file_management.read import ReadFileTool

                read_tool = ReadFileTool()

                # Process each file and collect its content
                for file in other_files:
                    try:
                        # Use the read_file tool with conversion enabled
                        result = read_tool._run(
                            file_path=file.path, convert_to_markdown=True
                        )

                        # Parse the result (JSON string)
                        import json

                        result_dict = json.loads(result)

                        if result_dict.get("content"):
                            file_content = result_dict["content"]
                            file_name = file.name or "Unnamed file"
                            # Add file content with a header
                            document_contents.append(
                                f"### File: {file_name}\n\n{file_content}\n\n"
                            )
                    except Exception as e:
                        logging.error(f"Error processing file {file.name}: {str(e)}")
                        document_contents.append(
                            f"### File: {file.name}\n\nError processing file: {str(e)}\n\n"
                        )
            except Exception as e:
                logging.error(f"Error importing tools: {str(e)}")

        # Combine document contents with user content
        combined_content = ""
        if document_contents:
            combined_content = (
                "## Attached Documents\n\n"
                + "".join(document_contents)
                + "\n## User Message\n\n"
                + user_content
            )
        else:
            combined_content = user_content

        # If there are images, prepare for multimodal content
        if images:
            # Initialize multimodal content with text
            formatted_content = [{"type": "text", "text": combined_content}]

            # Add images to multimodal content
            for image in images:
                with open(image.path, "rb") as img_file:
                    image_data = base64.b64encode(img_file.read()).decode("utf-8")
                    formatted_content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        }
                    )
            return HumanMessage(content=formatted_content)
        else:
            # Text-only content
            return HumanMessage(content=combined_content)
