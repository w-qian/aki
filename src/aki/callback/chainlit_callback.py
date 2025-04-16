"""
Independent Chainlit callback handler for managing UI updates without inheriting from Chainlit's implementation.
Focuses on three main areas:
1. Normal text streaming (assistant responses)
2. Thinking content (reasoning steps)
3. Tool execution steps
"""

import chainlit as cl
import logging
import traceback
import time
import json
import asyncio
import ast  # For safely evaluating Python literals
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.callbacks.base import AsyncCallbackHandler

logger = logging.getLogger("aki.custom_callback")


class ChainlitCallback(AsyncCallbackHandler):

    @staticmethod
    def _parse_input(input_data, tool_name=None):
        """
        Parse input data from either a string (JSON or Python literal) or a dict.

        Args:
            input_data: The input data to parse (string or dict)
            tool_name: Name of the tool for logging purposes

        Returns:
            Parsed dict or None if parsing failed
        """
        log_prefix = f"[{tool_name}] " if tool_name else ""

        if isinstance(input_data, dict):
            return input_data

        if not isinstance(input_data, str):
            logger.warning(
                f"{log_prefix}Cannot parse input of type: {type(input_data).__name__}"
            )
            return None

        # Try JSON parsing first
        try:
            return json.loads(input_data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(
                f"{log_prefix}JSON parsing failed: {str(e)}, trying ast.literal_eval"
            )

        # Fall back to Python literal parsing
        try:
            return ast.literal_eval(input_data)
        except (SyntaxError, ValueError) as e:
            logger.debug(f"{log_prefix}Python literal parsing failed: {str(e)}")
            return str(input_data)

    @staticmethod
    def _modify_batch_tool_name(tool_input):
        """
        Extract tool names from batch_tool input and create a formatted name.

        Args:
            tool_input: Parsed tool input dictionary

        Returns:
            Tuple of (modified_name, invocation_details)
            where invocation_details is a list of tool dictionaries with name and arguments
        """
        if not tool_input or not isinstance(tool_input, dict):
            return "batch_tool", []

        invocations = tool_input.get("invocations")
        if not invocations:
            return "batch_tool", []

        # Parse invocations if it's a string
        invocations_data = None
        if isinstance(invocations, list):
            invocations_data = invocations
        elif isinstance(invocations, str):
            invocations_data = ChainlitCallback._parse_input(
                invocations, "batch_tool.invocations"
            )

        if not isinstance(invocations_data, list):
            return "batch_tool", []

        # Extract tool names
        tool_names = [
            item.get("name")
            for item in invocations_data
            if isinstance(item, dict) and "name" in item
        ]

        if not tool_names:
            return "batch_tool", []

        return f"batch_tool[{', '.join(tool_names)}]", invocations_data

    @staticmethod
    def _modify_mcp_tool_name(tool_input):
        """
        Extract server_name and tool_name from mcp_tool input and create a formatted name.

        Args:
            tool_input: Parsed tool input dictionary

        Returns:
            Tuple of (modified_name, avatar_name)
        """
        if not tool_input or not isinstance(tool_input, dict):
            return "mcp_tool", "tool"

        server_name = tool_input.get("server_name", "")
        tool_name = tool_input.get("tool_name", "")

        if not server_name or not tool_name:
            return "mcp_tool", "tool"

        # Use amazon avatar for Amazon servers
        avatar_name = "amazon" if "amazon" in server_name.lower() else "tool"
        return f"mcp[{server_name}: {tool_name}]", avatar_name

    @staticmethod
    def _format_output_for_display(output, tool_name=None):
        """
        Format tool output for better display in the UI.

        Args:
            output: Raw output from the tool
            tool_name: Name of the tool for specific formatting

        Returns:
            Formatted output object
        """
        if not output:
            return output

        # Parse string output if needed
        output_obj = output
        if isinstance(output, str):
            try:
                output_obj = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                try:
                    output_obj = ast.literal_eval(output)
                except (SyntaxError, ValueError):
                    # Keep as string if parsing fails
                    return output

        # Specific formatting could be added here based on tool_name
        # For example, pretty formatting for search results, etc.

        return output_obj

    @staticmethod
    def _is_message_empty(message):
        """
        Check if a Chainlit message has empty content (after stripping whitespace).

        Args:
            message: Chainlit message object to check

        Returns:
            bool: True if message content is empty or just whitespace, False otherwise
        """
        if not message or not hasattr(message, "content"):
            return True

        content = message.content
        return not content or (isinstance(content, str) and not content.strip())

    """
    Custom callback handler built from scratch that integrates with Chainlit UI
    """

    @staticmethod
    def detect_reasoning_content(content: Any) -> Tuple[bool, Optional[str]]:
        """
        Detect if content contains reasoning and extract it.

        Args:
            content: Content to analyze, could be string, dict, or list

        Returns:
            Tuple of (is_reasoning, content_text)
        """
        # Handle string content
        if isinstance(content, str):
            return False, content

        # Handle structured content (most common for reasoning)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "reasoning_content":
                    # Extract reasoning content from block
                    if "reasoning_content" in block:
                        reasoning_data = block["reasoning_content"]
                        # Check for text content within reasoning
                        if (
                            isinstance(reasoning_data, dict)
                            and "text" in reasoning_data
                        ):
                            return True, reasoning_data["text"]

                        # Check for signature (end of reasoning)
                        elif (
                            isinstance(reasoning_data, dict)
                            and reasoning_data.get("type") == "signature"
                        ):
                            return True, None  # Signal end of reasoning

        # Handle direct reasoning block
        if isinstance(content, dict) and content.get("type") == "reasoning_content":
            reasoning_data = content.get("reasoning_content", {})
            if (
                isinstance(reasoning_data, dict)
                and reasoning_data.get("type") == "text"
                and "text" in reasoning_data
            ):
                return True, reasoning_data["text"]

        # Extract regular text content for non-reasoning blocks
        text_content = None
        if isinstance(content, dict) and content.get("type") == "text":
            if "text" in content and content["text"]:
                text_content = content["text"]
        elif isinstance(content, list):
            # Look for text blocks in a list
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    if "text" in block and block["text"]:
                        text_content = block["text"]
                elif isinstance(block, str):
                    text_content = block

        return False, text_content

    def __init__(self):
        """Initialize the callback handler with necessary state tracking."""
        super().__init__()
        self.response_message = None
        self.loading_message = None  # Track the loading message indicator
        self.thinking_step = None
        self.thinking_step_id = None  # Keep track of last thinking step ID
        self.tool_steps = {}
        self.active_tool_run_ids = set()
        self.start_time = time.time()
        self.in_thinking_mode = False
        self.seen_first_token = False
        self.thinking_queue = asyncio.Queue()
        self.thinking_task = None
        self.thinking_content = []
        self.current_author = "assistant"  # Default author
        self.current_run_id = None  # Track the current run ID for author mapping
        self.run_authors = {}  # Map run_ids to authors for consistent author tracking
        self.current_context_stack = (
            []
        )  # Track context stack for proper step sequencing
        self.creating_thinking_task = (
            False  # Flag to prevent race conditions in thinking step creation
        )

    async def _thinking_worker(self):
        """Worker that processes thinking content using context manager"""
        self.start_time = time.time()
        thinking_step_id = None

        # Use context manager for the thinking step
        async with cl.Step(
            name="Thinking...", default_open=True, metadata={"avatarName": "aki"}
        ) as thinking_step:
            # Store reference to the step
            self.thinking_step = thinking_step
            thinking_step_id = thinking_step.id

            # Process thinking content until end signal
            while True:
                # Get next content from queue with a timeout
                try:
                    content = await asyncio.wait_for(
                        self.thinking_queue.get(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    # Check if thinking mode ended externally
                    if not self.in_thinking_mode:
                        break
                    continue

                # Check for end signal
                if content is None:
                    break

                # Stream content to step
                await thinking_step.stream_token(content)
                self.thinking_content.append(content)

            # Update name with duration when done
            duration = round(time.time() - self.start_time)
            thinking_step.name = "Thought"

        # When context exits, step is automatically sent with updates
        logger.debug(f"Thinking step completed with duration: {duration}s")

        # Keep the ID for tool references even after thinking is done
        self.thinking_step = None
        self.thinking_step_id = thinking_step_id

    async def _ensure_response_message(self, author="assistant"):
        """Create response message if it doesn't exist or if author changed."""
        # If we have a loading message, update it instead of creating a new one
        if hasattr(self, "loading_message") and self.loading_message:
            if not self.response_message:
                logger.debug(
                    f"Reusing loading message as response message with author: {author}"
                )
                self.response_message = self.loading_message
                self.current_author = author
                # Clear the loading message reference since we've transferred it
                self.loading_message = None
                return

        # Log current state for debugging
        if self.response_message:
            current_author = getattr(self.response_message, "author", None)
            logger.debug(
                f"Current message author: {current_author}, New author: {author}"
            )
        else:
            logger.debug(f"No existing message, creating new with author: {author}")

        # Create new message if none exists or if author has changed
        if not self.response_message or author != self.current_author:
            logger.debug(
                f"Creating new message: current_author={self.current_author} -> new_author={author}"
            )

            # Clean up any existing loading message that wasn't used
            if hasattr(self, "loading_message") and self.loading_message:
                await self.loading_message.remove()
                self.loading_message = None
                logger.debug(
                    "Removed loading message before creating new response message"
                )

            # Use thinking step ID if available, whether from active step or stored ID
            parent_id = None
            if self.thinking_step and hasattr(self.thinking_step, "id"):
                parent_id = self.thinking_step.id
            elif self.thinking_step_id:
                parent_id = self.thinking_step_id

            if parent_id:
                self.response_message = cl.Message(
                    content="", author=author, parent_id=parent_id
                )
            else:
                self.response_message = cl.Message(content="", author=author)

            await self.response_message.send()
            # Update tracking
            self.current_author = author
            logger.debug(
                f"Created new message with author: {author} with parent: {parent_id}"
            )

    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs
    ):
        """Handle LLM start."""
        logger.debug("LLM start event with kwargs:")
        logger.debug(f"on_llm_start kwargs: {kwargs}")

        metadata = kwargs.get("metadata", {}) if kwargs is not None else {}
        logger.debug(f"on_llm_start metadata: {metadata}")

        self.seen_first_token = False
        self.in_thinking_mode = False
        self.current_author = "assistant"  # Reset to default author

        # Cancel existing thinking task if any
        if self.thinking_task and not self.thinking_task.done():
            # Signal worker to stop
            await self.thinking_queue.put(None)
            # Wait for task to complete
            try:
                await asyncio.wait_for(self.thinking_task, timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for previous thinking task to complete")

        # Reset state but preserve thinking_step_id for chain of thought
        self.start_time = time.time()
        self.thinking_queue = asyncio.Queue()
        self.thinking_task = None
        self.thinking_step = None
        self.thinking_content = []

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """
        Process streaming tokens, handling both reasoning content and regular text.
        Uses async with context manager pattern for thinking steps.
        """
        try:
            self.seen_first_token = True

            # Get chunk object which contains more structured content
            chunk = kwargs.get("chunk")
            # Get run_id and check if we have a saved author for it
            run_id = str(kwargs.get("run_id", "")) if kwargs is not None else ""

            # Get metadata for author info
            metadata = kwargs.get("metadata", {}) if kwargs is not None else {}

            # Log all available kwargs to diagnose the author issue
            logger.debug(f"on_llm_new_token kwargs: {kwargs}")

            # Try to get author from stored mapping first
            author = "assistant"
            if run_id and run_id in self.run_authors:
                author = self.run_authors[run_id]
                logger.debug(f"Using saved author '{author}' for run_id {run_id}")
            else:
                # Fallback to metadata
                author = metadata.get("langgraph_node", "assistant")
                logger.debug(f"Using metadata author: {author}")

            # Try to get content from chunk first (better structured data)
            content = None
            if chunk and hasattr(chunk, "content"):
                content = chunk.content
                logger.debug(f"Found chunk content type: {type(content)}")

            # If no chunk content, use the token directly
            if content is None:
                content = token

            # Detect if content is reasoning or regular text
            is_reasoning, extracted_content = self.detect_reasoning_content(content)

            # Process based on content type
            if is_reasoning and extracted_content:
                # This is reasoning content - handle with thinking step
                if not self.in_thinking_mode and not self.creating_thinking_task:
                    try:
                        # Set flag to prevent other tokens from creating thinking tasks
                        self.creating_thinking_task = True

                        # First reasoning token, enter thinking mode
                        self.in_thinking_mode = True

                        # If we have a loading message, remove it first
                        if hasattr(self, "loading_message") and self.loading_message:
                            await self.loading_message.remove()
                            self.loading_message = None

                        # Start thinking worker task with context manager
                        self.thinking_task = asyncio.create_task(
                            self._thinking_worker()
                        )
                        logger.debug("Started thinking worker task")
                    finally:
                        # Always reset the flag to prevent deadlocks
                        self.creating_thinking_task = False

                # Send content to thinking worker if in thinking mode and queue exists
                if (
                    self.in_thinking_mode
                    and hasattr(self, "thinking_queue")
                    and self.thinking_queue
                ):
                    await self.thinking_queue.put(extracted_content)

            elif extracted_content:
                # Regular content - end thinking if active
                if self.in_thinking_mode:
                    # End thinking mode
                    self.in_thinking_mode = False

                    # Signal thinking worker to stop
                    await self.thinking_queue.put(None)

                    # Wait for thinking to complete if task exists
                    if self.thinking_task and not self.thinking_task.done():
                        try:
                            await asyncio.wait_for(self.thinking_task, timeout=1.0)
                        except asyncio.TimeoutError:
                            logger.warning(
                                "Timeout waiting for thinking task to complete"
                            )

                # Stream to response message
                await self._ensure_response_message(author)
                await self.response_message.stream_token(extracted_content)
                logger.debug(
                    f"Streamed text content to message: {extracted_content[:50]}"
                )

        except Exception as e:
            logger.error(f"Error in on_llm_new_token: {str(e)}")
            logger.error(f"Detailed traceback: {traceback.format_exc()}")
            # Reset flag in case of error to prevent deadlocks
            self.creating_thinking_task = False

    async def on_chat_model_start(
        self, serialized: Dict[str, Any], messages: List[List[Any]], **kwargs
    ) -> None:
        """Handle chat model start - create initial loading indicator and capture metadata."""

        # Extract and save the langgraph_node/author information
        run_id = str(kwargs.get("run_id", "")) if kwargs is not None else ""
        if run_id and "metadata" in kwargs and kwargs["metadata"] is not None:
            author = kwargs["metadata"].get("langgraph_node", "assistant")
            self.run_authors[run_id] = author
            self.current_author = author  # Update current author
            self.current_run_id = run_id

        # Check if there's an existing loading message and remove it first
        # This prevents duplicate loading messages when the model is throttled
        if hasattr(self, "loading_message") and self.loading_message:
            logger.debug("Removing existing loading message before creating a new one")
            await self.loading_message.remove()
            self.loading_message = None

        # Create initial loading message that will be replaced later
        self.loading_message = cl.Message(content="", author=self.current_author)
        await self.loading_message.stream_token(" ")
        logger.debug(f"Created loading message with author: {self.current_author}")

        # Fall back to default implementation
        await self.on_llm_start(serialized, ["<chat_messages>"], **kwargs)

    async def on_llm_end(self, response, **kwargs) -> None:
        """Handle LLM completion for both streaming and non-streaming models."""
        try:
            # If we still have a loading message at this point (no tokens were streamed),
            # we should handle it appropriately
            if hasattr(self, "loading_message") and self.loading_message:
                logger.debug("Handling loading message at LLM end")
                # Check if the message is empty
                if self._is_message_empty(self.loading_message):
                    logger.debug(
                        "Found empty loading message, clearing reference without removal"
                    )
                    await self.loading_message.remove()
                    self.loading_message = None
                elif not self.seen_first_token:
                    # No tokens were streamed - will handle content through loading message
                    logger.debug("No tokens streamed, preparing to use loading message")
                    self.response_message = self.loading_message
                else:
                    # We've started streaming but loading message wasn't used, clean it up
                    logger.debug("Removing unused loading message")
                    await self.loading_message.remove()
                    self.loading_message = None

            # Handle non-streaming models (no tokens seen during generation)
            if not self.seen_first_token:
                logger.debug("Handling non-streaming model response")

                # Get content from the LLMResult structure
                content = None
                try:
                    # Navigate through nested structure to get the content
                    if hasattr(response, "generations") and response.generations:
                        # Access the first generation's message content
                        generation = response.generations[0][0]
                        if hasattr(generation, "message") and hasattr(
                            generation.message, "content"
                        ):
                            content = generation.message.content
                            logger.debug(
                                f"Successfully extracted content from LLMResult: {type(content)}"
                            )
                        else:
                            logger.warning(
                                "Message or content attribute not found in generation"
                            )
                except Exception as e:
                    logger.error(f"Error extracting content from response: {e}")

                if content is None:
                    logger.warning("No content found in response")
                    return

                # Get run_id and try to get author from saved mapping
                run_id = str(kwargs.get("run_id", "")) if kwargs is not None else ""

                # Get author information
                metadata = kwargs.get("metadata", {}) if kwargs is not None else {}
                logger.info(f"on_llm_end metadata: {metadata}")

                # Try to get author from stored mapping first
                author = "assistant"
                if run_id and run_id in self.run_authors:
                    author = self.run_authors[run_id]
                    logger.info(f"Using saved author '{author}' for run_id {run_id}")
                else:
                    # Fallback to metadata
                    author = metadata.get("langgraph_node", "assistant")
                    logger.info(f"Using metadata author: {author}")

                # Extract text content and reasoning content
                text_content = None
                reasoning_content = None

                # For list-type responses (like Deepseek)
                if isinstance(content, list):
                    logger.debug(f"Processing list content with {len(content)} items")
                    for item in content:
                        if isinstance(item, dict):
                            # Extract text content
                            if item.get("type") == "text" and "text" in item:
                                text_content = item["text"]
                                logger.debug(
                                    f"Found text content: {text_content[:50]}..."
                                )

                            # Extract reasoning content
                            elif (
                                item.get("type") == "reasoning_content"
                                and "reasoning_content" in item
                            ):
                                reasoning_data = item["reasoning_content"]
                                if (
                                    isinstance(reasoning_data, dict)
                                    and reasoning_data.get("type") == "text"
                                ):
                                    reasoning_content = reasoning_data.get("text")
                                    logger.debug(
                                        f"Found reasoning content: {reasoning_content[:50]}..."
                                    )

                # Display thinking step if reasoning content exists
                if reasoning_content:
                    # If we have a loading message, remove it first
                    if hasattr(self, "loading_message") and self.loading_message:
                        await self.loading_message.remove()
                        self.loading_message = None
                        logger.debug(
                            "Removed loading message before creating thinking step (non-streaming)"
                        )

                    async with cl.Step(
                        name="Thought", default_open=True
                    ) as thinking_step:
                        self.thinking_step = thinking_step
                        self.thinking_step_id = thinking_step.id
                        await thinking_step.stream_token(reasoning_content)
                        logger.debug("Created thinking step for non-streaming model")

                # Display text content if it exists
                if text_content:
                    # Update current author for tracking
                    self.current_author = author

                    # Get parent ID if thinking step exists
                    parent_id = self.thinking_step_id if self.thinking_step_id else None

                    # Create and send message
                    self.response_message = cl.Message(
                        content="", author=author, parent_id=parent_id
                    )
                    await self.response_message.send()
                    logger.debug(
                        f"Created new message with author: {author} with parent: {parent_id}"
                    )

                    # Add the text content
                    await self.response_message.stream_token(text_content)
                    logger.debug(
                        f"Displayed non-streaming text: {text_content[:50]}..."
                    )

            # Handle streaming models (finalize thinking if active)
            if self.in_thinking_mode:
                self.in_thinking_mode = False
                await self.thinking_queue.put(None)

                # Wait for thinking to complete
                if self.thinking_task and not self.thinking_task.done():
                    try:
                        await asyncio.wait_for(self.thinking_task, timeout=1.0)
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Timeout waiting for thinking task to complete during LLM end"
                        )

            # Finalize the response message if it exists to remove the animated dot
            if self.response_message:
                logger.debug("Finalizing response message to remove animated dot")
                await self.response_message.update()

        except Exception as e:
            logger.error(f"Error in on_llm_end: {str(e)}")
            logger.error(f"Detailed traceback: {traceback.format_exc()}")

    async def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs
    ) -> None:
        """Create and track tool steps."""
        try:
            # End thinking mode if active before starting tool
            if self.in_thinking_mode:
                self.in_thinking_mode = False
                await self.thinking_queue.put(None)

                # Wait for thinking to complete
                if self.thinking_task and not self.thinking_task.done():
                    try:
                        await asyncio.wait_for(self.thinking_task, timeout=1.0)
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Timeout waiting for thinking task to complete during tool start"
                        )

            run_id = str(kwargs.get("run_id", "") if kwargs is not None else "")
            if not run_id:
                logger.warning("Tool started without run_id")
                return

            # Get basic tool information
            name = serialized.get("name", "Tool") if serialized is not None else "Tool"
            avatar_name = "tool"  # Default avatar name

            # Log input_str for debugging
            logger.debug(
                f"Tool input for {name} (type: {type(input_str).__name__}): {input_str[:200] if isinstance(input_str, str) else str(input_str)[:200]}"
            )

            # Parse input using our helper function
            tool_input = self._parse_input(input_str, name)
            parsed_input = (
                tool_input  # Store a copy of the nicely parsed input for the UI
            )

            # Modify name and avatar based on tool type
            if name == "batch_tool" and tool_input:
                name, batch_details = self._modify_batch_tool_name(tool_input)
                logger.debug(f"Modified batch_tool name to: {name}")
            elif name == "mcp_tool" and tool_input:
                name, avatar_name = self._modify_mcp_tool_name(tool_input)
                logger.debug(
                    f"Modified mcp_tool name to: {name}, avatar: {avatar_name}"
                )
            elif "search" in name.lower():
                avatar_name = "search"

            if self.loading_message is not None and self._is_message_empty(
                self.loading_message
            ):
                logger.debug(
                    "Found empty loading message, clearing reference without removal"
                )
                await self.loading_message.remove()
                self.loading_message = None

            # Create the tool step
            async with cl.Step(
                name=name,
                type="tool",
                id=run_id,
                metadata={"avatarName": avatar_name},
                # parent_id=parent_id  # Make tools appear as siblings of the message
            ) as tool_step:
                # Set input to the nicely parsed version if available, otherwise use the raw input
                if parsed_input is not None:
                    tool_step.input = parsed_input
                elif input_str:
                    tool_step.input = input_str

                # Store and track the tool step
                self.tool_steps[run_id] = tool_step
                self.active_tool_run_ids.add(run_id)

            logger.debug(f"Created tool step for {name} with run_id {run_id}")

        except Exception as e:
            logger.error(f"Error in on_tool_start: {str(e)}")
            logger.error(f"Detailed traceback: {traceback.format_exc()}")

    async def on_tool_end(self, output: str, **kwargs) -> None:
        """Update tool step with output."""
        try:
            run_id = str(kwargs.get("run_id", "") if kwargs is not None else "")
            if not run_id or run_id not in self.tool_steps:
                logger.warning(f"Tool ended with unknown run_id: {run_id}")
                return

            tool_step = self.tool_steps[run_id]
            tool_name = tool_step.name if hasattr(tool_step, "name") else None

            # Format the output for better display using our helper function
            formatted_output = self._format_output_for_display(output, tool_name)
            tool_step.output = formatted_output

            # Update and remove from active set
            await tool_step.update()
            self.active_tool_run_ids.discard(run_id)
            logger.debug(f"Completed tool step for run_id {run_id}")

        except Exception as e:
            logger.error(f"Error in on_tool_end: {str(e)}")
            logger.error(f"Detailed traceback: {traceback.format_exc()}")

    async def on_tool_error(self, error: BaseException, **kwargs) -> None:
        """Handle tool errors."""
        run_id = str(kwargs.get("run_id", "") if kwargs is not None else "")
        if run_id and run_id in self.tool_steps:
            tool_step = self.tool_steps[run_id]

            # Set error state
            tool_step.is_error = True
            tool_step.output = str(error)

            # Update and remove from active set
            await tool_step.update()
            self.active_tool_run_ids.discard(run_id)
            logger.debug(f"Tool error for run_id {run_id}: {error}")

    # Handle chain events minimally - only create steps for important chains

    async def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs
    ) -> None:
        """Minimal chain handling."""
        pass

    async def on_chain_end(self, outputs: Dict[str, Any], **kwargs) -> None:
        """Minimal chain handling."""
        pass

    async def on_chain_error(self, error: BaseException, **kwargs) -> None:
        """Log chain errors."""
        if len(str(error)) > 0:
            logger.error(f"Chain error: {error}")
