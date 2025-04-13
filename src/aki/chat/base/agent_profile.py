"""Base implementation for chat profiles using a single agent with tools."""

import logging
import os
from typing import List, Optional, Dict

import chainlit as cl

from aki.console_print import print_debug
from aki.llm import token_counter
from ...profiles.prompts.memory_prompts import (
    INITIAL_SUMMARY_PROMPT,
    EXTEND_SUMMARY_PROMPT,
)
from chainlit.input_widget import Select, Switch, Slider
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AnyMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
    RemoveMessage,
    ToolMessage,
    trim_messages,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from .base_profile import BaseProfile
from .environment_details import EnvironmentDetails
from ..graph.agent_graph import AgentGraph, GraphConfig, AgentState
from ...config import constants
from ...config.profile_manager import ProfileManager
from ...llm import llm_factory
from aki.llm.capabilities import ModelCapability


class AgentProfile(BaseProfile):
    """Base class for chat profiles using a single agent with tools."""

    # Class-level cache for LLM instances
    _llm_cache = {}

    def __init__(self, profile_name: str):
        """Initialize the chat profile.

        Args:
            profile_name: Name of the profile to use
        """
        super().__init__()
        self.profile_name = profile_name
        self.profile_manager = ProfileManager()

        # Get profile configuration
        base_prompt = self.profile_manager.get_system_prompt(profile_name)
        env_prompt = EnvironmentDetails.ENVIRONMENT_PROMPT
        self.system_prompt = f"{base_prompt}\n\n{env_prompt}"
        self.rules_content = self.profile_manager.get_rules_content(profile_name)
        self.tools = self.profile_manager.get_tools(profile_name)
        self.capabilities = {ModelCapability.TEXT_TO_TEXT}

        # Initialize property for summary LLM - will be created on demand
        self._summary_llm = None

        # Initialize graph handler
        config = GraphConfig(chat_node_name=self.name())
        self.graph_handler = AgentGraph(
            state_type=AgentState,
            chat_node=self.chat_node,
            summary_node=self.summary_node,
            tool_routing=self.tool_routing,
            tools=self.tools,
            config=config,
        )

    def create_graph(self) -> StateGraph:
        """Create the graph with chat and tools nodes."""
        return self.graph_handler.create_graph()

    def _filter_messages(
        self, messages: List[AnyMessage], model_id: Optional[str] = None
    ) -> List[AnyMessage]:
        """Filter and fix messages for model compatibility."""
        result = []

        for msg in messages:
            # Skip messages with completely empty content arrays
            if (
                isinstance(msg, AIMessage)
                and isinstance(msg.content, list)
                and len(msg.content) == 0
            ):
                continue

            # For AIMessages with list content, handle reasoning content and empty text fields
            if isinstance(msg, AIMessage) and isinstance(msg.content, list):
                # Only filter out reasoning_content items if model_id contains deep_seek
                filtered_content = []
                for item in msg.content:
                    # Keep reasoning content unless model_id contains deep_seek
                    if not (
                        isinstance(item, dict)
                        and item.get("type") == "reasoning_content"
                        and model_id
                        and "deepseek" in model_id.lower()
                    ):
                        filtered_content.append(item)

                # Find any text content items that are empty after filtering
                has_empty_text = False
                for content_item in filtered_content:
                    if (
                        isinstance(content_item, dict)
                        and content_item.get("type") == "text"
                        and (
                            content_item.get("text") is None
                            or content_item.get("text").strip() == ""
                        )
                    ):
                        has_empty_text = True
                        break

                # If there's an empty text item AND we have tool calls, remove the text item entirely
                if has_empty_text and any(
                    item.get("type") == "tool_use"
                    for item in filtered_content
                    if isinstance(item, dict)
                ):
                    # Create a new filtered content list with only non-empty text items and tool calls
                    new_content = []
                    for item in filtered_content:
                        if not (
                            isinstance(item, dict)
                            and item.get("type") == "text"
                            and (
                                item.get("text") is None
                                or item.get("text").strip() == ""
                            )
                        ):
                            new_content.append(item)
                    msg.content = new_content
                # If there's an empty text item but no tools, add a meaningful placeholder
                elif has_empty_text:
                    for item in filtered_content:
                        if (
                            isinstance(item, dict)
                            and item.get("type") == "text"
                            and (
                                item.get("text") is None
                                or item.get("text").strip() == ""
                            )
                        ):
                            item["text"] = "*"
                else:
                    # Use the filtered content
                    msg.content = filtered_content

            # Add the message (original or with fixed content) to results
            result.append(msg)

        return result

    async def _process_with_fallback(
        self,
        llm: BaseChatModel,
        messages: List[AnyMessage],
        state: AgentState,
        config: RunnableConfig,
    ) -> List:
        """Process messages with retry logic for long inputs."""
        try:
            # Prepare input messages with system message first
            input_messages = [SystemMessage(self.get_system_prompt(state))]

            # Insert rules as the first human message if available and state includes first_run flag
            if self.rules_content:
                input_messages.append(HumanMessage(content=self.rules_content))

            # Add the rest of the messages
            input_messages.extend(messages)

            result = await llm.with_retry(
                wait_exponential_jitter=True, stop_after_attempt=2
            ).ainvoke(input=input_messages, config=config)

            return [result]

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error in LLM invocation: {error_msg}")
            logging.info("Trying to recover...")
            return await self._fallback_invoke(llm, messages, config)

    def _remove_unmatched_tool_messages(
        self, messages: List[AnyMessage]
    ) -> List[AnyMessage]:
        """Remove AI messages that contain tool calls without matching tool responses."""
        # First identify which AI messages have unmatched tool calls
        unmatched_ai_messages = set()
        tool_calls_map = {}

        # Identify all tool calls with their source messages
        for i, msg in enumerate(messages):
            if (
                isinstance(msg, AIMessage)
                and hasattr(msg, "tool_calls")
                and msg.tool_calls
            ):
                for call in msg.tool_calls:
                    tool_calls_map[call["id"]] = i

        # Remove tool calls that have responses
        for msg in messages:
            if isinstance(msg, ToolMessage) and hasattr(msg, "tool_call_id"):
                if msg.tool_call_id in tool_calls_map:
                    del tool_calls_map[msg.tool_call_id]

        # Mark AI messages with unmatched tool calls
        for tool_id, msg_index in tool_calls_map.items():
            unmatched_ai_messages.add(msg_index)

        # Filter out the problematic messages
        return [msg for i, msg in enumerate(messages) if i not in unmatched_ai_messages]

    async def _fallback_invoke(
        self, llm: BaseChatModel, messages: List[AnyMessage], config: RunnableConfig
    ) -> List:
        # Check for the specific validation error case
        cleaned_messages = self._remove_unmatched_tool_messages(messages)
        if len(messages) - len(cleaned_messages) > 0:
            logging.info(
                f"Removed {len(messages) - len(cleaned_messages)} messages with unmatched tools"
            )

        logging.info("Starting conversation summarization")
        # Get summary using async invoke with complete tool context
        summary_prompt = (
            "You will be feeding a chat history between user and AI because somehow the conversation crashed."
            "Your goal is to make it not noticeable to the user"
            "Try your best to keep helping the user"
        )

        trimmed_messages = trim_messages(
            self._filter_messages(cleaned_messages),
            strategy="last",
            token_counter=token_counter.tiktoken_counter,
            max_tokens=constants.DEFAULT_TOKEN_THRESHOLD,
            start_on="human",
            end_on=("human", "tool"),
            allow_partial=False,
        )

        # Prepare input messages with system message
        input_messages = [SystemMessage(content=summary_prompt)]

        # Add rules as the first human message if available
        # We don't check first_run here because this is a recovery method
        if self.rules_content:
            input_messages.append(HumanMessage(content=self.rules_content))
            logging.debug(f"Added rules in fallback invocation for {self.profile_name}")

        # Add trimmed messages
        input_messages.extend(trimmed_messages)
        result = await llm.ainvoke(input=input_messages, config=config)

        # Create removal messages for the history
        delete_messages = [
            RemoveMessage(id=m.id) for m in messages if not isinstance(m, HumanMessage)
        ]
        # Return only human messages and the last AI message
        return [result] + delete_messages

    def _get_reasoning_config(
        self, model_name: str, state: Optional[Dict] = None
    ) -> Dict:
        """Get reasoning configuration based on model capabilities and state.

        Configuration hierarchy (highest to lowest precedence):
        1. Runtime state (UI settings) - flat keys first, then nested
        2. Model capability check
        3. Global constants

        Args:
            model_name: Name of the model
            state: Optional state dictionary containing model settings

        Returns:
            Dict containing reasoning configuration
        """
        config = {
            "enable": constants.DEFAULT_REASONING_ENABLED,
            "budget_tokens": constants.DEFAULT_BUDGET_TOKENS,
        }

        try:
            supports_reasoning = (
                ModelCapability.EXTENDED_REASONING
                in llm_factory.get_model_capabilities(model_name)
            )

            if supports_reasoning and state:
                config.update(
                    {
                        "enable": state["reasoning_enabled"],
                        "budget_tokens": state["budget_tokens"],
                    }
                )
            elif supports_reasoning:
                config["enable"] = True
        except Exception as e:
            logging.warning(f"Error checking model capabilities for {model_name}: {e}")

        logging.debug(f"Final reasoning config: {config}")
        return config

    def _get_llm(self, state: Optional[Dict] = None) -> BaseChatModel:
        """Get LLM instance from cache or create new one.

        Args:
            state: Optional state dictionary containing model settings

        Returns:
            BaseChatModel: The LLM instance
        """
        if not state:
            return self._get_default_llm()

        # Try to get model_id from flat key first
        model_id = None
        if "model_id" in state:
            model_id = state["model_id"]
            logging.debug(f"Using model_id from flat key: {model_id}")
        else:
            logging.warning("No model_id found in state, using default model")
            return self._get_default_llm()

        # Get reasoning configuration
        reasoning_config = self._get_reasoning_config(model_id, state)
        # Create model with reasoning settings if enabled
        kwargs = {}
        if reasoning_config["enable"]:
            kwargs.update(
                {
                    "enable_reasoning": True,
                    "budget_tokens": reasoning_config["budget_tokens"],
                }
            )
            logging.debug(
                f"Creating LLM with reasoning enabled, budget_tokens: {reasoning_config['budget_tokens']}"
            )

        model_capabilities = llm_factory.get_model_capabilities(model_id)
        supports_tools = ModelCapability.TOOL_CALLING in model_capabilities

        # Set tools based on model capabilities
        tools_to_use = []
        if supports_tools and self.tools:
            tools_to_use = self.tools
            logging.debug(
                f"Model {model_id} supports tools, providing {len(tools_to_use)} tools"
            )
        else:
            if not supports_tools:
                logging.info(f"Model {model_id} doesn't support tools")
                logging.info(f"Tools disabled for profile {self.profile_name}")

        # Create and cache new instance
        # Get the settings from state
        # Default to True for prompt cache if model is compatible
        enable_cache = (
            state.get("enable_prompt_cache", True)
            and model_id
            and ("sonnet" in model_id.lower() or "haiku" in model_id.lower())
        )

        # Get temperature from state or default to 0.6 (Note: Extended thinking will override this to 1.0)
        temperature = float(state.get("temperature", 0.6))

        llm = llm_factory.create_model(
            name=self.output_chat_model,
            model=model_id,
            tools=tools_to_use,
            enable_prompt_cache=enable_cache,
            temperature=temperature,
            **kwargs,
        )
        return llm

    async def chat_node(self, state: AgentState, config: RunnableConfig) -> AgentState:
        """Process chat messages using the configured LLM."""
        logging.debug(f"chat_node: Processing with state: {state}")

        # Get LLM for this state
        llm = self._get_llm(state)

        # Pass model_id to _filter_messages
        model_id = state.get("model_id")
        filtered_messages = self._filter_messages(state["messages"], model_id)

        messages = await self._process_with_fallback(
            llm, filtered_messages, state, config
        )
        return {"messages": messages}

    # Method removed - environment details are now added to system prompt instead

    async def summary_node(
        self, state: AgentState, config: RunnableConfig
    ) -> AgentState:
        # Log token threshold information before summarization
        logging.info(
            "Start to summarize conversation because we are breaching the token threshold"
        )

        summary = state.get("summary", "")
        if summary:
            # If a summary exists, use the extend prompt
            summary_message = EXTEND_SUMMARY_PROMPT.format(existing_summary=summary)
        else:
            # For initial summary, use the initial prompt
            summary_message = INITIAL_SUMMARY_PROMPT

        filtered_messages = self._filter_messages(
            state["messages"], model_id=constants.DEFAULT_MODEL
        )

        messages = filtered_messages + [HumanMessage(content=summary_message)]

        # Lazy-initialize summary LLM if it doesn't exist yet
        if not self._summary_llm:
            default_model = constants.DEFAULT_MODEL
            # Get settings from state, defaulting to enable prompt cache if model is compatible
            enable_cache = (
                state.get("enable_prompt_cache", True)
                and default_model
                and (
                    "sonnet" in default_model.lower()
                    or "haiku" in default_model.lower()
                )
            )

            # Get temperature from state or default to 0.6 (Note: Extended thinking will override this to 1.0)
            temperature = float(state.get("temperature", 0.6))

            self._summary_llm = llm_factory.create_model(
                "_summer",
                default_model,
                tools=self.tools,
                enable_prompt_cache=enable_cache,
                temperature=temperature,
            ).with_retry(
                wait_exponential_jitter=True,
                stop_after_attempt=3,
            )

        response = await self._summary_llm.ainvoke(messages, config)

        # Extract the text content properly based on response structure
        summary_text = ""
        if hasattr(response, "content"):
            if isinstance(response.content, list):
                # Handle list-type content (extract text from the first item)
                for item in response.content:
                    if isinstance(item, dict) and "text" in item:
                        summary_text += item["text"]
            else:
                # Handle string content
                summary_text = response.content

        print_debug(f"Summary of previous conversations: {summary_text}")
        delete_messages = self.find_delete_messages(state["messages"])

        if hasattr(cl, "user_session") and cl.user_session:
            # Reset the flag in UsageCallback
            callback = cl.user_session.get("usage_callback", None)
            if callback:
                callback.current_total_tokens = 0

        logging.debug("Reset conversations")

        # Store summary as a string, not as the raw content object
        return {"summary": summary_text, "messages": delete_messages}

    def find_delete_messages(self, all_messages):
        return [RemoveMessage(id=m.id) for m in all_messages]

    def get_system_prompt(self, state):
        """Get the system prompt with environment details."""
        # Get base prompt
        base_prompt = self.system_prompt

        # Add summary if available
        summary = state.get("summary", "")
        if summary:
            summary_str = summary if isinstance(summary, str) else str(summary)
            base_prompt = (
                f"{base_prompt} \n Summary of conversation earlier: {summary_str}"
            )

        # Add environment details
        env = state.get("environment")
        if env:
            # Update workspace info
            workspace_dir = state.get("workspace_dir", os.getcwd())
            env.update_workspace(workspace_dir)

            # Get environment string with task list if available
            task_list = state.get("task_list", "")
            env_details = env.to_string(task_list)

            # Append to prompt - using a clear separator
            return f"{base_prompt}\n\n{'-' * 3}\n\n{env_details}"

        return base_prompt

    def create_default_state(self) -> AgentState:
        """Create the default state for the chat profile."""
        # Get profile configuration
        profile_config = self.profile_manager.get_profile_config(self.profile_name)
        default_model = profile_config.get("default_model", constants.DEFAULT_MODEL)
        reasoning_config = profile_config.get("reasoning_config", {})

        # Check if default model supports reasoning
        supports_reasoning = False
        try:
            supports_reasoning = (
                ModelCapability.EXTENDED_REASONING
                in llm_factory.get_model_capabilities(default_model)
            )
            logging.debug(
                f"create_default_state: Model {default_model} supports_reasoning={supports_reasoning}"
            )
        except Exception as e:
            logging.warning(f"Error checking model capabilities: {e}")

        # Create state with flat keys
        state = {
            "name": self.name(),
            "messages": [],
            "task_list": "",
            "environment": EnvironmentDetails(),
            "model_id": default_model,
            "reasoning_enabled": reasoning_config.get(
                "default_enabled", constants.DEFAULT_REASONING_ENABLED
            ),
            "budget_tokens": reasoning_config.get(
                "budget_tokens", constants.DEFAULT_BUDGET_TOKENS
            ),
            "enable_prompt_cache": True,  # Default to True for prompt cache
            "temperature": 0.6,  # Default temperature value
            "first_run": True,  # Flag to indicate first run for rules insertion
        }
        return state

    @classmethod
    def name(cls) -> str:
        """Get the name of the chat profile."""
        return cls._profile_name

    @classmethod
    def chat_profile(cls) -> cl.ChatProfile:
        """Get chat profile configuration."""
        return ProfileManager().get_chat_profile(cls._profile_name)

    @property
    def chat_settings(self) -> cl.ChatSettings:
        """Configure chat settings with model selection and extended reasoning options."""
        # Get profile configuration
        profile_config = self.profile_manager.get_profile_config(self.profile_name)
        default_model = profile_config.get("default_model", constants.DEFAULT_MODEL)
        reasoning_config = profile_config.get("reasoning_config", {})

        all_models = sorted(llm_factory.list_models(capabilities=self.capabilities))

        # Create settings with model selector - using flat keys
        settings = [
            Select(
                id="model_id",
                label="Chat Model",
                values=all_models,
                initial_value=default_model,
            ),
        ]
        # Add settings for reasoning
        settings.extend(
            [
                Switch(
                    id="reasoning_enabled",
                    label="Enable Extended Reasoning (Only valid for Claude 3.7)",
                    description="Turn on Claude's extended reasoning capability for complex problems",
                    initial=reasoning_config.get(
                        "default_enabled", constants.DEFAULT_REASONING_ENABLED
                    ),
                ),
                Slider(
                    id="budget_tokens",
                    label="Budget tokens",
                    description="Budget tokens for extended reasoning (min: 1024)",
                    min=1024,
                    max=8192,
                    step=256,
                    initial=reasoning_config.get(
                        "budget_tokens", constants.DEFAULT_BUDGET_TOKENS
                    ),
                ),
                # Add new prompt cache setting
                Switch(
                    id="enable_prompt_cache",
                    label="Enable Prompt Cache",
                    description="Enable prompt caching for Claude 3.7 Sonnet and Claude 3.5 Haiku models",
                    initial=True,
                ),
                # Add new temperature setting
                Slider(
                    id="temperature",
                    label="Temperature",
                    description="Control randomness in responses (0=deterministic, 1=creative). Note: Extended thinking will override this to 1.0",
                    min=0,
                    max=1,
                    step=0.1,
                    initial=0.6,
                ),
            ]
        )
        return cl.ChatSettings(settings)
