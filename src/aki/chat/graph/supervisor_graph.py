"""Graph creation for supervisor-based multi-agent chat profiles."""

from langgraph.graph import StateGraph
from typing import Annotated, Sequence, List, Any, Callable, Dict, TypedDict, Union
from dataclasses import dataclass
from langchain_core.messages import AnyMessage, AIMessage
from langchain.tools import BaseTool
import re
import operator


class SupervisorState(TypedDict):
    """State with messages and next agent routing."""

    messages: Annotated[Sequence[AnyMessage], operator.add]  # Message history
    next: str  # Will be constrained by Literal in concrete implementations
    chat_profile: str


@dataclass
class SupervisorConfig:
    """Configuration for supervisor-based multi-agent graph creation."""

    supervisor_node_name: str = "supervisor"
    entry_point: str = None  # If None, will use supervisor_node_name


class SupervisorGraph:
    """Handles graph creation for supervisor-based multi-agent chat profiles."""

    def __init__(
        self,
        state_type: Any,
        supervisor_node: Callable,
        tool_routing: Callable,
        agent_nodes: Dict[str, Callable],
        agent_tools: Dict[str, List[BaseTool]],
        config: SupervisorConfig = None,
    ):
        """Initialize the graph handler.

        Args:
            state_type: The state type class for the graph
            supervisor_node: The supervisor node processing function
            agent_nodes: Dictionary of agent names to their node functions
            agent_tools: Dictionary of agent names to their tool lists
            config: Optional graph configuration
        """
        self.state_type = state_type
        self.supervisor_node = supervisor_node
        self.agent_nodes = agent_nodes
        self.agent_tools = agent_tools
        self.tool_routing = tool_routing
        self.config = config or SupervisorConfig()
        self._graph = None

    def create_graph(self) -> StateGraph:
        """Create the graph with supervisor, agent nodes, and tool nodes."""
        graph = StateGraph(self.state_type)

        # Add supervisor node
        graph.add_node(self.config.supervisor_node_name, self.supervisor_node)

        # Add agent nodes
        for agent_name, node_fn in self.agent_nodes.items():
            graph.add_node(agent_name, node_fn)

        # Add edges - all agents report back to supervisor
        for agent_name in self.agent_nodes.keys():
            graph.add_conditional_edges(agent_name, lambda state: state["next"])

        # Route based on supervisor's decision
        graph.add_conditional_edges(
            self.config.supervisor_node_name, lambda state: state["next"]
        )

        # Set entry point
        entry_point = self.config.entry_point or self.config.supervisor_node_name
        graph.set_entry_point(entry_point)

        self._graph = graph
        return graph

    def get_graph(self) -> StateGraph:
        """Get the current graph instance, creating it if necessary."""
        if self._graph is None:
            self._graph = self.create_graph()
        return self._graph

    def extract_valid_mention(self, response: Union[str, list, dict]) -> str | None:
        """Extract valid agent mention from content."""
        # Create mapping of normalized names to original names
        valid_names = {
            self._normalize_name(name): name for name in self.agent_nodes.keys()
        }

        # Extract text based on content type
        text_to_search = ""
        if isinstance(response, str):
            text_to_search = response
        elif isinstance(response, list):
            # Handle list of dictionaries
            for message in response:
                if isinstance(message, AIMessage):
                    for content in message.content:
                        if content["type"] == "text":
                            text_to_search += content["text"] + "\n"
                elif isinstance(message, dict):
                    text_to_search += message["text"] + "\n"
        elif isinstance(response, dict) and "text" in response:
            text_to_search = response["text"]

        # Find all @mentions using regex
        mentions = re.findall(r"@(\w+)[,\s.!?]*", text_to_search)

        # Check each mention against valid names
        for mention in mentions:
            normalized = self._normalize_name(mention)
            if normalized in valid_names:
                return valid_names[normalized]

        # No valid mentions found
        return "__end__"

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        return re.sub(r"[^\w\s]", "", name).lower().strip()
