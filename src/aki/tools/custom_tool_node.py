"""Custom Tool Node implementation with enhanced timeout, response handling, and parameter name conversion."""

import asyncio
import logging
import os
import tiktoken
from typing import Any, Dict, List, Optional, Union, Sequence
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

# Import shared parameter conversion utilities
from aki.config.constants import DEFAULT_MAX_TOOL_TOKENS, DEFAULT_TOKENIZER_MODEL
from aki.tools.param_conversion import (
    identify_tools_needing_conversion,
    convert_tool_args,
)


class ToolTimeoutError(Exception):
    """Exception raised when a tool execution exceeds the timeout limit."""

    pass


class ResponseTooLargeError(Exception):
    """Exception raised when a tool response exceeds the token limit."""

    pass


class CustomToolNode(ToolNode):
    """
    Enhanced ToolNode that adds:
    1. Timeout and response size management while maintaining parallel execution
    2. Parameter name conversion between camelCase and snake_case

    Inherits from langgraph's ToolNode to keep the parallel execution benefits.

    Configuration:
    - Timeout: Configurable via AKI_TOOL_TIME_OUT_THRESHOLD environment variable (default: 60 seconds)
    - Parameter conversion: Enabled by default
    """

    def __init__(
        self,
        tools: Sequence[Union[BaseTool, callable]],
        *,
        timeout: Optional[int] = None,
        enable_param_conversion: bool = True,
        **kwargs,
    ) -> None:
        """Initialize the custom tool node.

        Args:
            tools: List of tools to be made available
            timeout: Override default timeout from environment
            enable_param_conversion: Whether to automatically convert camelCase to snake_case
                for tool parameters
            **kwargs: Additional arguments passed to ToolNode
        """
        super().__init__(tools, **kwargs)

        # Load timeout with precedence:
        # 1. Constructor argument
        # 2. Environment variable
        # 3. Default value (60)
        self.timeout = timeout or int(os.getenv("AKI_TOOL_TIME_OUT_THRESHOLD", "60"))

        # Initialize tokenizer with fixed settings
        self.max_tokens = DEFAULT_MAX_TOOL_TOKENS
        self.tokenizer = tiktoken.get_encoding(DEFAULT_TOKENIZER_MODEL)

        # Parameter conversion settings
        self.enable_param_conversion = enable_param_conversion
        self.tools_with_param_conversion = identify_tools_needing_conversion(tools)

        logging.debug(
            f"Initialized CustomToolNode with:"
            f"\n  - {len(tools)} tools"
            f"\n  - {self.timeout}s timeout"
            f"\n  - {self.max_tokens} max tokens (fixed)"
            f"\n  - Parameter conversion: {self.enable_param_conversion}"
        )

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the configured tokenizer."""
        return len(self.tokenizer.encode(text))

    def truncate_content(self, content: Any) -> Any:
        """Truncate content if it exceeds token limit."""
        if isinstance(content, str):
            tokens = self.tokenizer.encode(content)
            logging.debug(f"Tool response tokens: {len(tokens)}")
            if len(tokens) > self.max_tokens:
                truncated = self.tokenizer.decode(tokens[: self.max_tokens])
                return (
                    truncated
                    + f"\n\n[TRUNCATED: Response exceeded {self.max_tokens} tokens]"
                )
            return content
        elif isinstance(content, dict):
            return {k: self.truncate_content(v) for k, v in content.items()}
        elif isinstance(content, list):
            return [self.truncate_content(item) for item in content]
        return content

    def truncate_tool_message(self, message: ToolMessage) -> ToolMessage:
        """Truncate content in a ToolMessage."""
        if not hasattr(message, "content"):
            return message
        message.content = self.truncate_content(message.content)
        return message

    def _convert_tool_args(self, tool_call: Dict) -> Dict:
        """Convert tool call arguments from camelCase to snake_case."""
        if not self.enable_param_conversion:
            return tool_call

        result = tool_call.copy()
        result["args"] = convert_tool_args(
            tool_call["name"],
            tool_call.get("args", {}),
            self.tools_with_param_conversion,
        )

        return result

    async def _arun_one(
        self,
        call: Dict,
        input_type: str,
        config: RunnableConfig,
    ) -> ToolMessage:
        """Run a single tool with parameter name conversion."""
        # Convert camelCase parameter names to snake_case if needed
        call = self._convert_tool_args(call)

        # Pass to the parent implementation
        return await super()._arun_one(call, input_type, config)

    def _run_one(
        self,
        call: Dict,
        input_type: str,
        config: RunnableConfig,
    ) -> ToolMessage:
        """Run a single tool synchronously with parameter name conversion."""
        # Convert camelCase parameter names to snake_case if needed
        call = self._convert_tool_args(call)

        # Pass to the parent implementation
        return super()._run_one(call, input_type, config)

    async def _afunc(
        self,
        input: Union[List[AIMessage], Dict[str, Any], Any],
        config: RunnableConfig,
        *,
        store: Optional[Any] = None,
    ) -> Any:
        """Enhanced async execution with timeout and truncation."""
        try:
            # Apply timeout to the entire batch of tool executions
            async with asyncio.timeout(self.timeout):
                # Execute tools in parallel using parent ToolNode
                outputs = await super()._afunc(input, config, store=store)

                # Handle different output formats
                if isinstance(outputs, list):
                    # Truncate each tool message
                    outputs = [
                        (
                            self.truncate_tool_message(output)
                            if isinstance(output, ToolMessage)
                            else output
                        )
                        for output in outputs
                    ]
                elif isinstance(outputs, dict):
                    # Handle dict format (usually with "messages" key)
                    if "messages" in outputs:
                        outputs["messages"] = [
                            (
                                self.truncate_tool_message(msg)
                                if isinstance(msg, ToolMessage)
                                else msg
                            )
                            for msg in outputs["messages"]
                        ]

                return outputs

        except asyncio.TimeoutError:
            # Create timeout response based on input format
            error_msg = f"Tool execution exceeded {self.timeout} seconds timeout"
            logging.warning(error_msg)

            # Get tool calls from input
            if isinstance(input, list):
                last_message = input[-1]
            elif isinstance(input, dict) and "messages" in input:
                last_message = input["messages"][-1]
            else:
                last_message = None

            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                # Create timeout responses for each tool call
                timeout_responses = [
                    ToolMessage(
                        content=error_msg,
                        name=call["name"],
                        tool_call_id=call["id"],
                        status="error",
                    )
                    for call in last_message.tool_calls
                ]
                return (
                    timeout_responses
                    if isinstance(input, list)
                    else {"messages": timeout_responses}
                )

            # Fallback error response
            return {"error": error_msg}

        except Exception as e:
            error_msg = f"Error executing tools: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return {"error": error_msg}

    def invoke(self, *args, **kwargs):
        """Synchronous invocation is not supported."""
        raise NotImplementedError(
            "CustomToolNode only supports async invocation. Use ainvoke instead."
        )
