"""
LangGraph callback handler for emitting metrics using UsageMetrics.
Tracks metrics for LLM queries, tool executions, and errors.
"""

import logging
import time
from typing import Any, Dict, List
from datetime import datetime

from langchain_core.callbacks.base import AsyncCallbackHandler
import chainlit as cl


from aki.config.paths import get_aki_home
from aki.config import constants
from aki.console_print import print_debug

logger = logging.getLogger("usage_callback")


class UsageCallback(AsyncCallbackHandler):
    """
    Callback handler that emits metrics using UsageMetrics.
    Tracks LLM usage, tool executions, and errors.
    """

    def __init__(self, metrics):
        """Initialize the metrics callback.

        Args:
            metrics: UsageMetrics instance to use for recording metrics.
        """
        super().__init__()
        self.metrics = None
        self.model_map = {}
        self.current_total_tokens = 0
        self.token_threshold = constants.DEFAULT_TOKEN_THRESHOLD
        self.cached_read = 0
        self.cached_write = 0

        # TTFT tracking
        self.start_time = 0
        self.first_token_time = None
        self.ttft_ms = None

    def get_usage_display(
        self,
        usage_metadata: Dict = None,
        latency_ms: float = None,
        ttft_ms: float = None,
    ) -> str:
        """Return a concise formatted string with token usage, latency, cache info, and TTFT.

        Args:
            usage_metadata: Dictionary containing token usage information
            latency_ms: Latency in milliseconds
            ttft_ms: Time to first token in milliseconds

        Returns:
            str: Concise formatted string with usage summary
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        total_tokens = 0
        cache_read = 0
        cache_write = 0

        # Extract data from usage_metadata if available
        if usage_metadata:
            input_tokens = usage_metadata.get("input_tokens", 0)
            output_tokens = usage_metadata.get("output_tokens", 0)
            total_tokens = usage_metadata.get(
                "total_tokens", input_tokens + output_tokens
            )
            self.current_total_tokens = total_tokens

            # Get cache information
            cache_details = usage_metadata.get("input_token_details", {})
            cache_read = cache_details.get("cache_read", 0)
            cache_write = cache_details.get("cache_creation", 0)

        # Format components
        components = [f"[{timestamp}] LLM: {total_tokens:,} tokens"]

        # Add latency
        # if latency_ms is not None:
        #     latency_s = latency_ms / 1000.0
        #     components.append(f"{latency_s:.2f}s")

        # Add cache info
        components.append(f"Cache: {cache_write:,} write / {cache_read:,} read")

        # Add TTFT if available (prefer self.ttft_ms if available)
        ttft_to_use = self.ttft_ms if self.ttft_ms is not None else ttft_ms
        if ttft_to_use is not None:
            ttft_s = ttft_to_use / 1000.0
            components.append(f"Time to first token: {ttft_s:.2f}s")

        # Join all components with separators
        return " | ".join(components)

    def need_summarization(self) -> bool:
        """Check if conversation needs summarization based on token count.

        Returns:
            bool: True if current token count exceeds threshold, False otherwise
        """
        # Log current token status for debugging
        logger.debug(
            f"Token status: current={self.current_total_tokens}, threshold={self.token_threshold}"
        )
        return self.current_total_tokens >= self.token_threshold

    def _get_run_id(self, kwargs: Dict[str, Any]) -> str:
        """Extract run ID from kwargs, defaulting to a placeholder if not found."""
        run_id = kwargs.get("run_id", "unknown_run_id")
        return str(run_id)

    def _get_stored_version(self):
        version_file = get_aki_home() / "version"
        if not version_file.exists():
            return "0.0.0"
        return version_file.read_text().strip()

    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Record start time for LLM query."""
        run_id = self._get_run_id(kwargs)

        # Extract model name from serialized input
        model_id = serialized.get("kwargs", {}).get("model_id", "unknown_model")
        self.model_map[run_id] = model_id

        # Record model usage using helper function
        # self.metrics.record_model_usage(model_id)

        # Start timing for TTFT measurement
        self.start_time = time.time()
        self.first_token_time = None
        self.ttft_ms = None

    async def on_chat_model_start(
        self, serialized: Dict[str, Any], messages: List[List[Any]], **kwargs: Any
    ) -> None:
        """Handle chat model start and reset timers for TTFT calculation."""
        # Start timing for TTFT measurement
        self.start_time = time.time()
        self.first_token_time = None
        self.ttft_ms = None

        # Call parent implementation
        await super().on_chat_model_start(serialized, messages, **kwargs)

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Capture first token timing for TTFT calculation."""
        # If this is the first token, record the time and calculate TTFT
        if self.first_token_time is None:
            self.first_token_time = time.time()
            self.ttft_ms = (self.first_token_time - self.start_time) * 1000
            logger.debug(f"Calculated TTFT: {self.ttft_ms:.2f}ms")

    async def on_llm_end(self, response, **kwargs) -> None:
        """Record LLM usage metrics including token counts and execution time."""
        run_id = self._get_run_id(kwargs)
        # Extract token usage from response
        try:
            model_id = self.model_map.get(run_id, "unknown_model")
            # Get usage metadata
            usage_metadata = response.generations[0][0].message.usage_metadata
            input_tokens = usage_metadata.get("input_tokens", 0)
            output_tokens = usage_metadata.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens

            # Update token tracking
            self.current_total_tokens = total_tokens

            # Get execution time from response metadata
            response_metadata = response.generations[0][0].message.response_metadata
            metrics = response_metadata.get("metrics", {})
            execution_time_ms = metrics.get("latencyMs", 0)

            # Use helper functions for token and execution time metrics
            # self.metrics.record_token_usage(model_id, input_tokens, output_tokens)
            # self.metrics.record_execution_time(model_id, execution_time_ms)

            # Print formatted token usage summary with our manually calculated TTFT
            print_debug(
                self.get_usage_display(usage_metadata, execution_time_ms, self.ttft_ms)
            )

            logger.debug(
                f"Token metrics recorded for model {model_id}: input={input_tokens}, output={output_tokens}, time={execution_time_ms}ms, ttft={self.ttft_ms}ms"
            )

            # Check if summarization is needed
            if self.need_summarization():
                # Mark that summarization is needed in user_session
                if hasattr(cl, "user_session") and cl.user_session:
                    cl.user_session.set("need_summarize", True)
                    logger.info(
                        f"Marking conversation for summarization: tokens={self.current_total_tokens}"
                    )

        except Exception as e:
            logger.debug(f"Failed to record token metrics: {e}")

    async def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Record tool usage metric."""
        pass
        # Get tool name
        # tool_name = (
        #     serialized.get("name", "unknown_tool")
        #     if serialized is not None
        #     else "unknown_tool"
        # )
        # Use helper function for tool usage
        # self.metrics.record_tool_usage(tool_name)

    async def on_tool_end(self, output: str, **kwargs) -> None:
        # todo record tool token
        pass

    async def on_tool_error(self, error: BaseException, **kwargs) -> None:
        # todo: record tool failed metrics
        pass
