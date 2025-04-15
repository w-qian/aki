"""EventHandler for Aki application."""

import os
import logging
import json

import chainlit as cl
from chainlit.types import ThreadDict
from langchain.schema.runnable.config import RunnableConfig
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import Runnable

from aki.persistence.dal import StateDAL
from aki.persistence.database_factory import db_manager
from aki.chat.profile_factory import BaseProfile, ProfileFactory
from aki.callback.chainlit_callback import ChainlitCallback
from aki.callback.usage_callback import UsageCallback
from aki.chat.export_conversation import (
    handle_export_command,
    register_export_command,
)


class EventHandler:
    """Handles all Chainlit events and maintains application state."""

    def __init__(self, usage_callback=None):
        """Initialize the event handler with required components.

        Args:
            usage_callback: Optional custom usage callback. If None, a default will be created.
        """
        self.profile_factory = ProfileFactory()
        self.chainlit_callback = ChainlitCallback()

        # Use provided usage_callback or create default
        self.usage_callback = (
            usage_callback
            if usage_callback is not None
            else UsageCallback(metrics=None)
        )

    def setup_data_layer(self):
        """Set up the data persistence layer."""
        if not db_manager:
            logging.info("Chat history is disabled. Not registering data layer.")
            return None
        return db_manager.get_adapter()

    async def setup_chat_profiles(self):
        """Load available chat profiles."""
        logging.debug("Loading chat profiles")
        profiles = []

        # Get all available profiles
        for profile_class in self.profile_factory.get_available_profiles().values():
            if hasattr(profile_class, "chat_profile"):
                profiles.append(profile_class.chat_profile())

        return profiles

    def header_auth_callback(self, headers: dict) -> cl.User | None:
        """Handle header-based authentication."""
        return cl.User(
            identifier="admin", metadata={"role": "admin", "provider": "credentials"}
        )

    async def start_chat(self, chat_profile: str, state: dict | None = None):
        """Start or resume a chat session.

        Args:
            chat_profile: The name of the chat profile to use
            state: Optional state to resume from
        """

        # Set initialization flag to False initially
        cl.user_session.set("graph_initialized", False)

        try:
            profile = self.get_or_create_profile(chat_profile)
            graph = profile.create_graph()
            compiled_graph = graph.compile()
            cl.user_session.set("graph", compiled_graph)
            # Set flag to indicate successful initialization
            cl.user_session.set("graph_initialized", True)
            logging.debug("[start_chat] Graph compiled and set to session")

            if state:
                # Resume from previous state
                state["chat_profile"] = chat_profile  # Ensure chat_profile is in state
                cl.user_session.set("state", state)
                await profile.get_chat_settings(state)
            else:
                # Create new state
                state = profile.create_default_state()
                state["chat_profile"] = chat_profile
                cl.user_session.set("state", state)
                # Get and apply settings
                settings = await profile.get_chat_settings()
                await self.handle_settings_update(settings)

            logging.debug(
                f"[start_chat] Completed. Final state: {cl.user_session.get('state')}"
            )
        except Exception as e:
            logging.error(f"[start_chat] Failed to initialize chat: {e}", exc_info=True)
            raise

    async def handle_chat_start(self):
        """Handle chat start event."""
        logging.debug("Chat start event triggered")
        app_user = cl.user_session.get("user")
        logging.debug(
            f"[on_chat_start] User: {app_user.identifier if app_user else 'Unknown'}"
        )

        # Use default profile if none selected
        chat_profile = getattr(cl.context.session, "chat_profile", None)
        logging.debug(
            f"[on_chat_start] Initial chat_profile from session: {chat_profile}"
        )

        if chat_profile is None:
            chat_profile = self.profile_factory.get_default_profile()
            logging.debug(f"[on_chat_start] Using default profile: {chat_profile}")

        try:
            await self.start_chat(chat_profile)
            await register_export_command()
        except Exception as e:
            logging.error(
                f"[on_chat_start] Failed to initialize chat: {e}", exc_info=True
            )
            await cl.Message(
                content="Sorry, there was a problem setting up your chat session. Please try a new conversation."
            ).send()

    async def handle_settings_update(self, settings: cl.ChatSettings):
        """Handle settings update event."""
        state = cl.user_session.get("state")
        logging.debug(f"[on_settings_update] Current state: {state}")
        logging.debug(f"[on_settings_update] Updating with settings: {settings}")

        for key in settings.keys():
            if key in state:
                state[key] = settings[key]

        cl.user_session.set("state", state)
        logging.debug(
            f"[on_settings_update] Updated state: {cl.user_session.get('state')}"
        )

    async def handle_stop(self):
        """Handle stop event."""
        messages = cl.user_session.get("state")["messages"]
        message = messages[-1]
        # Check if last message contains tool_use
        if isinstance(message, AIMessage) and message.tool_calls:
            logging.debug(f"[on_stop] Found tool_use in last message: {messages[-1]}")
            for tool_call in message.tool_calls:
                tool_result = (json.dumps({"error": "Tool execution aborted by user"}),)
                messages.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )
                logging.debug(
                    f"[on_stop] {tool_call['name']} \nInput: {tool_call['args']}, \nOutput: {tool_result}"
                )

        assistant_contents = []
        for message in reversed(cl.chat_context.to_openai()):
            if message["role"] != "assistant":
                break
            assistant_contents.append(message["content"])
        message = (
            "Conversation is stopped by user. You might be in the wrong direction or taking too much time. Ask users how to better help them. Below is the message that is shown to the user: "
            + "\\n".join(reversed(assistant_contents))
        )
        logging.debug(f"[on_stop] Adding assistant message: {message}")
        messages.append(AIMessage(content=message))

        # Update loading message to remove the animation
        if (
            hasattr(self.chainlit_callback, "loading_message")
            and self.chainlit_callback.loading_message
        ):
            await self.chainlit_callback.loading_message.remove()

        # Update thinking step to remove the animation
        if (
            hasattr(self.chainlit_callback, "in_thinking_mode")
            and self.chainlit_callback.in_thinking_mode
        ):
            self.chainlit_callback.in_thinking_mode = False
            # Signal the thinking worker to complete
            await self.chainlit_callback.thinking_queue.put(None)

        # Update any active response message to remove the animation
        if (
            hasattr(self.chainlit_callback, "response_message")
            and self.chainlit_callback.response_message
        ):
            await self.chainlit_callback.response_message.update()

    async def handle_chat_end(self):
        """Handle chat end event and save state if needed."""
        # Check if chat history is enabled in configuration
        chat_history_enabled = (
            os.getenv("AKI_CHAT_HISTORY_ENABLED", "false").lower() == "true"
        )
        if not chat_history_enabled:
            logging.debug("Chat history is disabled. Not saving state.")
            return

        if not db_manager:  # No database manager available
            logging.debug("No database manager available. Not saving state.")
            return

        state = cl.user_session.get("state")
        thread_id = cl.context.session.thread_id

        if state:
            try:
                async with db_manager.get_session() as session:
                    state_dal = StateDAL(session)
                    await state_dal.upsert_state(
                        thread_id=thread_id,
                        state=state,
                    )
            except Exception as e:
                logging.error(f"Failed to save state: {e}", exc_info=True)

    async def handle_chat_resume(self, thread: ThreadDict):
        """Handle chat resume event."""
        # Check if chat history is enabled in configuration
        if not db_manager:
            logging.debug(
                "[on_chat_resume] Chat history is disabled. Starting new chat."
            )
            # Fall back to default profile
            default_profile = self.profile_factory.get_default_profile()
            logging.debug(f"[on_chat_resume] Using default profile: {default_profile}")
            await self.start_chat(default_profile)
            return

        try:
            async with db_manager.get_session() as session:
                state_dal = StateDAL(session)
                state = await state_dal.get_state(thread["id"])

                if state and "chat_profile" in state:
                    logging.debug(
                        f"[on_chat_resume] Resuming with state for chat profile: {state.get('chat_profile')}"
                    )
                    cl.user_session.set("state", state)
                    await self.start_chat(state["chat_profile"], state)
                else:
                    logging.warning(
                        f"[on_chat_resume] Retrieved invalid state (None or missing chat_profile): {state}"
                    )
                    # Fall back to default profile
                    default_profile = self.profile_factory.get_default_profile()
                    logging.debug(
                        f"[on_chat_resume] Using default profile: {default_profile}"
                    )
                    await self.start_chat(default_profile)
        except Exception as e:
            logging.error(f"Failed to resume chat: {e}", exc_info=True)

    async def handle_message(self, message: cl.Message):
        """
        Process user messages using astream_events with reliable state updates.
        """

        # Check for special command to export conversation
        if message.command == "Export":
            await handle_export_command(message)
            return

        graph: Runnable = cl.user_session.get("graph")
        state = cl.user_session.get("state")

        logging.debug(f"[on_message] Current state: {state}")

        # Validate required objects
        if graph is None:
            logging.error("[on_message] Graph is None! Cannot process message.")
            await cl.Message(
                content="Sorry, there was a problem processing your message. Please try refreshing the page."
            ).send()
            return

        # Check if graph initialization is complete
        graph_initialized = cl.user_session.get("graph_initialized", False)
        if not graph_initialized:
            logging.warning(
                "[on_message] Graph initialization not yet complete. Asking user to wait."
            )
            await cl.Message(
                content="Chat initialization is still in progress. Please wait a moment and try again."
            ).send()
            return

        if state is None:
            logging.error("[on_message] State is None!")
            await cl.Message(
                content="Sorry, there was a problem with your session. Please try refreshing the page."
            ).send()
            return

        if "chat_profile" not in state:
            logging.error(f"[on_message] chat_profile missing from state: {state}")
            await cl.Message(
                content="Sorry, there was a problem with your chat configuration. Please try starting a new chat."
            ).send()
            return

        graph.name = state["chat_profile"]

        # Get profile for message formatting
        profile = self.get_or_create_profile(state["chat_profile"])

        # Validate the message before processing
        if not self.is_valid_message(message):
            logging.warning(
                "[on_message] Invalid message received - no text and no images"
            )
            await cl.Message(
                content="Please provide a message with text or at least one image."
            ).send()
            return

        # Format and add the validated message to state
        formatted_message = profile.format_message(message)
        state["messages"] += [formatted_message]
        config = {
            "configurable": {"thread_id": cl.context.session.id},
            "callbacks": [self.chainlit_callback, self.usage_callback],
            "recursion_limit": 500,
        }

        try:
            # Process events from the graph
            async for output in graph.astream_events(
                state, version="v2", config=RunnableConfig(**config)
            ):
                # Handle state updates from events
                if (
                    output["event"] == "on_chain_end"
                    and output["name"] in graph.nodes.keys()
                    and output["name"] not in {"__start__", "__end__"}
                ):
                    # Update state with node outputs
                    for key, value in output["data"]["output"].items():
                        if isinstance(value, str):
                            state[key] = value
                        elif isinstance(value, list):
                            if key not in state:
                                state[key] = []
                            state[key] += value

                elif output["event"] == "on_chain_end" and output["name"] == graph.name:
                    # Merge final LangGraph output with existing state
                    state.update(output["data"]["output"])

            # Finalize response message if it exists
            if self.chainlit_callback.response_message:
                await self.chainlit_callback.response_message.update()

            # Save updated state
            cl.user_session.set("state", state)

        except Exception as e:
            error_msg = f"An error occurred: {e!s}."
            logging.error(error_msg, exc_info=True)
            fix_suggestion = "Please try a new conversation or report the issue in the github issue tracker."
            await cl.Message(content=f"{error_msg} {fix_suggestion}").send()

    def get_or_create_profile(self, chat_profile: str) -> BaseProfile:
        """Get cached profile instance or create a new one.

        Args:
            chat_profile: Name of the chat profile

        Returns:
            An instance of the requested chat profile
        """
        profile_key = f"profile_{chat_profile}"
        profile = cl.user_session.get(profile_key)

        if profile is None:
            logging.debug(f"Creating new profile instance for {chat_profile}")
            profile = self.profile_factory.create_profile(chat_profile)
            cl.user_session.set(profile_key, profile)

        return profile

    def is_valid_message(self, message: cl.Message) -> bool:
        """Check if a message is valid for processing.

        A message is considered valid if it has either:
        1. Non-empty text content OR
        2. At least one image element
        """
        # Check if message has non-empty text content
        has_text = message.content is not None and message.content.strip() != ""

        # Check if message has any image elements
        has_images = False
        if message.elements:
            for element in message.elements:
                if "image" in element.mime:
                    has_images = True
                    break

        # Message is valid if it has either text or images
        return has_text or has_images
