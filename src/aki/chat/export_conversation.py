"""
Export conversation history feature for Aki.

This implementation provides conversation export in markdown (for better readability) and JSON (include more metadata) formats.
"""

import json
import logging
from enum import Enum
from typing import Dict, Optional, Any, Callable, Awaitable

import chainlit as cl
from chainlit.action import Action


# For JSON serialization
class MessageEncoder(json.JSONEncoder):
    """Custom JSON encoder for message objects."""

    def default(self, obj):
        # Extract common attributes from objects
        if hasattr(obj, "__dict__"):
            # Convert message objects to dictionaries
            result = {}
            for key, value in obj.__dict__.items():
                # Skip internal attributes
                if not key.startswith("_"):
                    result[key] = value
            return result

        # Use standard encoder for other types
        return super().default(obj)


logger = logging.getLogger(__name__)

# Type definitions
ExportFunction = Callable[[str, Dict[str, Any]], Awaitable[str]]


class ExportFormat(Enum):
    """Export format options."""

    JSON = "json"
    MARKDOWN = "md"


class ConversationExporter:
    """Handles exporting conversation history in markdown and JSON formats."""

    @staticmethod
    def _convert_message(msg: Any) -> Dict[str, Any]:
        """Convert a message object to a serializable dictionary."""
        # Case 1: Already a dictionary
        if isinstance(msg, dict):
            return msg

        # Case 2: Has author and content attributes (Chainlit Message)
        if hasattr(msg, "author") and hasattr(msg, "content"):
            result = {
                "author": getattr(msg, "author", "unknown"),
                "content": getattr(msg, "content", ""),
            }

            # Add additional attributes if present
            for attr in ["created_at", "name", "id", "type"]:
                if hasattr(msg, attr) and getattr(msg, attr) is not None:
                    result[attr] = getattr(msg, attr)

            return result

        # Case 3: Has type or role attributes (LangChain or OpenAI message)
        if hasattr(msg, "type") or hasattr(msg, "role"):
            result = {}

            # Common attributes to check for
            for attr in ["type", "role", "content", "name", "id"]:
                if hasattr(msg, attr) and getattr(msg, attr) is not None:
                    result[attr] = getattr(msg, attr)

            # If it has a dict representation, use it as base
            if hasattr(msg, "dict") and callable(getattr(msg, "dict")):
                try:
                    result.update(msg.dict())
                except Exception:
                    pass

            return result

        # Case 4: Just stringify the object if we can't extract info
        return {"content": str(msg)}

    @staticmethod
    async def export_as_json(
        thread_id: str, state: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export conversation as JSON."""
        if state is None:
            state = cl.user_session.get("state", {})

        # Convert messages to serializable dictionaries
        messages = []
        for msg in state.get("messages", []):
            messages.append(ConversationExporter._convert_message(msg))

        # Create the conversation data structure
        conversation_data = {
            "thread_id": thread_id,
            "chat_profile": state.get("chat_profile", "Unknown"),
            "messages": messages,
        }

        # Use custom encoder for any remaining complex objects
        return json.dumps(conversation_data, indent=2, cls=MessageEncoder)

    @staticmethod
    async def export_as_markdown(
        thread_id: str, state: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export conversation as Markdown."""
        if state is None:
            state = cl.user_session.get("state", {})

        # Get OpenAI formatted messages
        openai_messages = cl.chat_context.to_openai()

        md_content = f"# Aki Conversation - {thread_id}\n\n"

        # Add profile info
        chat_profile = state.get("chat_profile", "Unknown")
        md_content += f"**Profile:** {chat_profile}\n\n"

        # Add conversation
        md_content += "## Conversation\n\n"

        for msg in openai_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user":
                md_content += f"### User\n\n{content}\n\n"
            elif role == "assistant":
                md_content += f"### Assistant\n\n{content}\n\n"
            elif role == "system":
                md_content += f"### System\n\n{content}\n\n"

        return md_content


async def setup_export_button():
    """Set up the export actions."""
    # The export functionality will be set up when needed rather than
    # automatically at the start of each conversation
    pass


async def show_export_options():
    """Show export options when explicitly requested by the user."""
    thread_id = cl.context.session.thread_id

    logger.debug(f"Show export options - thread_id: {thread_id}")

    export_json = Action(
        name="export_json",
        label="Export as JSON",
        description="Export conversation as JSON file",
        payload={},
    )

    export_markdown = Action(
        name="export_markdown",
        label="Export as Markdown",
        description="Export conversation as Markdown file",
        payload={},
    )

    # Create a message with actions
    msg = cl.Message(
        content="**🔽 Export Options**\nClick to download conversation in your preferred format:",
        author="system",
        actions=[export_json, export_markdown],
    )
    await msg.send()


# Initialize the module-level format mapping
FORMAT_MAPPING = {
    "j": (ExportFormat.JSON, ConversationExporter.export_as_json),
    "json": (ExportFormat.JSON, ConversationExporter.export_as_json),
    "m": (ExportFormat.MARKDOWN, ConversationExporter.export_as_markdown),
    "markdown": (ExportFormat.MARKDOWN, ConversationExporter.export_as_markdown),
}


async def handle_direct_export(format_param: str) -> bool:
    """Handle direct export with a format parameter."""
    logger.debug(f"Direct export requested with format: {format_param}")

    # Normalize the format parameter
    format_param = format_param.strip().lower()

    if format_param not in FORMAT_MAPPING:
        # Format not recognized, return False to show options instead
        logger.warning(f"Invalid export format: {format_param}")
        return False

    # Get the format and export function
    export_format, export_function = FORMAT_MAPPING[format_param]

    # Call the generic handler with the appropriate format and function
    await handle_export(export_format, export_function)
    return True


async def handle_export(
    export_format: ExportFormat, export_function: ExportFunction
) -> None:
    """Generic handler for exporting conversations."""
    thread_id = cl.context.session.thread_id
    state = cl.user_session.get("state")

    format_name = export_format.name.lower()
    file_ext = export_format.value

    # Log state information
    logger.debug(f"Export {format_name} - Thread ID: {thread_id}")
    logger.debug(f"Export {format_name} - State available: {bool(state)}")

    try:
        # Create a message to show we're working on it
        msg = cl.Message(content=f"Preparing {format_name} export...")
        await msg.send()

        # Get the content
        content = await export_function(thread_id, state)

        # Check if we got content
        if not content or content.strip() == "":
            logger.error(f"Generated {format_name} content is empty")
            # Create a new message with error
            await cl.Message(
                content="❌ Failed to export conversation: No content found"
            ).send()
            return

        # Now send the file with the message ID as for_id
        mime_types = {
            ExportFormat.JSON.value: "application/json",
            ExportFormat.MARKDOWN.value: "text/markdown",
        }

        await cl.File(
            name=f"conversation_{thread_id}.{file_ext}",
            content=content.encode(),
            mime=mime_types.get(file_ext, "text/plain"),
            filename=f"conversation_{thread_id}.{file_ext}",
            description=f"Conversation exported as {format_name}",
        ).send(for_id=msg.id)

        # Create a new success message instead of updating (which has the bug)
        await cl.Message(
            content=f"✅ Conversation exported successfully as {format_name}"
        ).send()

    except Exception as e:
        logger.error(
            f"Failed to export conversation as {format_name}: {e}", exc_info=True
        )
        await cl.Message(content=f"❌ Failed to export conversation: {e}").send()


@cl.action_callback("export_json")
async def export_json_callback(action: Action):
    """Handle export as JSON action."""
    await handle_export(ExportFormat.JSON, ConversationExporter.export_as_json)


@cl.action_callback("export_markdown")
async def export_markdown_callback(action: Action):
    """Handle export as Markdown action."""
    await handle_export(ExportFormat.MARKDOWN, ConversationExporter.export_as_markdown)


async def register_export_command():
    """Register the export command in the Chainlit UI."""
    await cl.context.emitter.set_commands(
        [
            {
                "id": "Export",
                "description": "Export chat as file. Type 'j' for JSON or 'm' for Markdown.",
                "icon": "download",
            }
        ]
    )


async def handle_export_command(message: cl.Message) -> bool:
    """Handle the export command from app.py"""
    # Check if a format parameter was provided
    stripped_content = message.content.strip() if message.content else None
    if stripped_content:
        # Try to handle direct export with the provided format
        try:
            if (
                len(stripped_content) > 50
            ):  # Maximum reasonable length for a format parameter
                logger.warning(
                    f"Export format parameter too long: {len(stripped_content)} characters"
                )
                await cl.Message(
                    "Format parameter too long. Showing export options..."
                ).send()
                await show_export_options()
                return True

            if await handle_direct_export(stripped_content):
                # If handled successfully, return
                return True

            # Log and notify user about unrecognized format
            logger.warning(f"Unrecognized export format: {stripped_content}")
            await cl.Message("Format not recognized, showing options...").send()
        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            await cl.Message("Export failed, showing options...").send()

    # If no parameter or unrecognized format, show options
    await show_export_options()
    return True
