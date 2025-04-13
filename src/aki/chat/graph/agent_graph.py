"""Graph creation and visualization for single agent chat profiles."""

from langgraph.graph import StateGraph, END
from typing import List, Optional, Any, Callable
from dataclasses import dataclass
import chainlit as cl

from ..base.base_profile import BaseState
from ..base.environment_details import EnvironmentDetails
from ...tools import CustomToolNode


class AgentState(BaseState):
    # Model name of the chatbot
    task_list: str
    summary: str
    workspace_dir: Optional[str]
    environment: Optional[EnvironmentDetails]
    model_id: str
    reasoning_enabled: bool
    budget_tokens: int
    enable_prompt_cache: bool
    temperature: float


@dataclass
class GraphConfig:
    """Configuration for the graph creation."""

    chat_node_name: str = "Aki"
    entry_point: str = None  # If None, will use chat_node_name
    tool_node_name: str = "tools"
    summary_node_name: str = "summary_node"


def routing(state: AgentState):
    """Route to tools node if the last message has tool calls."""
    if messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")

    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return GraphConfig.tool_node_name

    """Route to summary node if the total token is beyond threshold."""
    # Check user_session for summarization flag
    need_summarize = False
    if hasattr(cl, "user_session") and cl.user_session:
        need_summarize = cl.user_session.get("need_summarize", False)
        if need_summarize:
            cl.user_session.set("need_summarize", False)  # Reset flag
            return GraphConfig.summary_node_name

    return END


class AgentGraph:
    """Handles graph creation and visualization for single agent chat profiles."""

    def __init__(
        self,
        state_type: Any,
        chat_node: Callable,
        summary_node: Callable,
        tool_routing: Callable,
        tools: Optional[List] = None,
        config: Optional[GraphConfig] = None,
    ):
        """Initialize the graph handler.

        Args:
            state_type: The state type class for the graph
            chat_node: The chat node processing function
            tool_routing: The tool routing function
            tools: Optional list of tools the agent can use
            config: Optional graph configuration
        """
        self.state_type = state_type
        self.chat_node = chat_node
        self.summary_node = summary_node
        self.tool_routing = tool_routing
        self.tools = tools or []
        self.config = config or GraphConfig()
        self._graph = None

    def create_graph(self) -> StateGraph:
        """Create the graph with chat and tools nodes."""
        graph = StateGraph(self.state_type)

        # Add nodes
        graph.add_node(self.config.chat_node_name, self.chat_node)
        graph.add_node(self.config.tool_node_name, CustomToolNode(self.tools))
        graph.add_node(self.config.summary_node_name, self.summary_node)

        # Set entry point
        entry_point = self.config.entry_point or self.config.chat_node_name
        graph.set_entry_point(entry_point)

        # Add edges
        graph.add_conditional_edges(self.config.chat_node_name, routing)
        graph.add_edge(self.config.tool_node_name, self.config.chat_node_name)
        graph.add_edge(self.config.summary_node_name, END)

        self._graph = graph
        return graph

    def get_graph(self) -> StateGraph:
        """Get the current graph instance, creating it if necessary."""
        if self._graph is None:
            self._graph = self.create_graph()
        return self._graph
