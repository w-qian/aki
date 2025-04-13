"""Supervisor-based team implementation with Aki as coordinator."""

import logging
import operator
import os
from pprint import pprint
import chainlit as cl
from typing import List, Literal, TypedDict
from chainlit.input_widget import Select
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, AnyMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableConfig
from typing import Annotated, Sequence
from langchain_core.tools import BaseTool
from aki.tools.web_search import create_web_search_tool

from ....config.constants import DEFAULT_MODEL
from ....tools.tool_executor import ToolExecutor
from ...base.base_profile import BaseProfile
from ....llm import llm_factory, ModelCapability
from ....tools.router import create_router_tool
from ....tools.render_html import create_render_html_tool
from ....tools.code_executor import create_execute_python_tool
from ....tools.tasklist_manager import create_tasklist_tool
from ....tools.file_management.toolkit import FileManagementToolkit
from ...graph.supervisor_graph import SupervisorGraph, SupervisorConfig
from pathlib import Path


class AkiTeamState(TypedDict):
    """State for Aki Team"""

    next: Literal["Aki", "Akisa", "Akira", "Akita", "__end__"]
    current_agent: str  # Tracks which agent is currently active
    messages: Annotated[Sequence[AnyMessage], operator.add]
    akira_messages: Annotated[Sequence[AnyMessage], operator.add]
    akisa_messages: Annotated[Sequence[AnyMessage], operator.add]
    akita_messages: Annotated[Sequence[AnyMessage], operator.add]
    chat_profile: str
    workspace_dir: str


class AkiTeamProfile(BaseProfile):
    """Profile implementation for Aki team mode."""

    def __init__(self, profile_name=None):  # Make profile_name optional
        super().__init__()
        self.capabilities = {ModelCapability.TEXT_TO_TEXT}
        self._aki_llm = None
        self._akisa_llm = None
        self._akira_llm = None
        self._akita_llm = None
        self._graph_handler = None
        self.supervisor_tool_executor = None
        self.developer_tool_executor = None
        self.researcher_tool_executor = None
        self.tester_tool_executor = None

    def _load_prompt(self, filename: str) -> str:
        """Load a prompt file from the prompts directory."""
        prompt_path = (
            Path(__file__).parent.parent.parent.parent
            / "profiles"
            / "prompts"
            / filename
        )
        if not prompt_path.exists():
            error_msg = f"Prompt file not found: {filename}"
            logging.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            with open(prompt_path) as f:
                content = f.read()
                if not content.strip():
                    error_msg = f"Prompt file is empty: {filename}"
                    logging.error(error_msg)
                    raise ValueError(error_msg)
                return content
        except Exception as e:
            error_msg = f"Failed to load prompt file {filename}: {str(e)}"
            logging.error(error_msg)
            raise type(e)(error_msg) from e

    def get_aki_tools(self) -> List[BaseTool]:
        """Get tools for Aki."""
        return [create_router_tool(), create_render_html_tool(), create_tasklist_tool()]

    def get_akisa_tools(self) -> List[BaseTool]:
        """Get tools for Akisa."""
        file_toolkit = FileManagementToolkit()
        return file_toolkit.get_tools()

    def get_akira_tools(self) -> List[BaseTool]:
        """Get tools for Akira."""
        web_search_tool = create_web_search_tool()
        return [web_search_tool]

    def get_akita_tools(self) -> List[BaseTool]:
        """Get tools for Akita."""
        return [create_execute_python_tool()]

    @property
    def aki_llm(self):
        if self._aki_llm is None:
            # Add router tool to supervisor's toolkit
            supervisor_tools = self.get_aki_tools()
            aki_llm = llm_factory.create_model(
                self.output_chat_model,
                model=cl.user_session.get("state").get("aki_model"),
            )
            self._aki_llm = aki_llm.bind_tools(tools=supervisor_tools)
            self.supervisor_tool_executor = ToolExecutor(supervisor_tools)
        return self._aki_llm

    @property
    def akisa_llm(self):
        if self._akisa_llm is None:
            developer_tools = self.get_akisa_tools()
            akisa_llm = llm_factory.create_model(
                self.output_chat_model,
                model=cl.user_session.get("state").get("akisa_model"),
            )
            akisa_llm = akisa_llm.bind_tools(tools=developer_tools)
            self.developer_tool_executor = ToolExecutor(developer_tools)
        return akisa_llm

    @property
    def akira_llm(self):
        if self._akira_llm is None:
            researcher_tools = self.get_akira_tools()
            akira_llm = llm_factory.create_model(
                self.output_chat_model,
                model=cl.user_session.get("state").get("akira_model"),
            )
            akira_llm = akira_llm.bind_tools(tools=researcher_tools)
            self.researcher_tool_executor = ToolExecutor(researcher_tools)
        return akira_llm

    @property
    def akita_llm(self):
        if self._akita_llm is None:
            tester_tools = self.get_akita_tools()
            akita_llm = llm_factory.create_model(
                self.output_chat_model,
                model=cl.user_session.get("state").get("akita_model"),
            )
            akita_llm = akita_llm.bind_tools(tools=tester_tools)
            self.tester_tool_executor = ToolExecutor(tester_tools)
        return akita_llm

    @property
    def graph_handler(self):
        if self._graph_handler is None:
            config = SupervisorConfig(supervisor_node_name="Aki")

            # Create agent nodes
            agent_nodes = {
                "Akisa": self.developer_node,
                "Akira": self.researcher_node,
                "Akita": self.tester_node,
            }

            # Create tool mappings
            agent_tools = {
                "Akisa": self.get_akisa_tools(),
                "Akira": self.get_akira_tools(),
                "Akita": self.get_akita_tools(),
            }

            self._graph_handler = SupervisorGraph(
                state_type=AkiTeamState,
                supervisor_node=self.supervisor_node,
                tool_routing=self.tool_routing,
                agent_nodes=agent_nodes,
                agent_tools=agent_tools,
                config=config,
            )
        return self._graph_handler

    def normalize_response(self, response):
        return response.content

    async def supervisor_node(
        self, state: AkiTeamState, config: RunnableConfig
    ) -> AkiTeamState:
        """Supervisor node that uses router tool for explicit control flow"""
        logging.debug("Entering supervisor node")
        logging.debug(f"Initial state: {state}")
        logging.debug(f"Config: {config}")
        ROUTER_PROMPT = """
        You have access to below tools:
        1. router - Use this to:
           - Direct tasks to appropriate team members:
             * Akira for research and information gathering
             * Akisa for implementation and development
             * Akita for testing and quality assurance
           - End the conversation when the task is complete
        2. render_html - Use this to render HTML content to the user
           - Provide HTML content to display
           - Useful for showing web content, visualizations, or formatted output
        3. tasklist - Use this to breakdown tasks and provide a clear tracker for user
           - Remember to mark tasks as running before delegate tasks to others
           - Only you have permissions to update task progress. Use this tool frequently so the user know how the team work is going. 
           
        Always use the router tool for routing decisions.
        Use render html tool to present the final work if you are asked to build a web application.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=self._load_prompt("aki_team.txt") + ROUTER_PROMPT
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        chain: Runnable = prompt | self.aki_llm
        try:
            response = await chain.ainvoke(state, config=config)
        except Exception as e:
            logging.error(f"Error in supervisor node: {e}", exc_info=True)
            raise

        # Handle tool calls and routing
        if hasattr(response, "tool_calls") and response.tool_calls:
            logging.debug(f"response: {response}")
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})

                if tool_name == "router":
                    return self._handle_router_execution(response, tool_args)

                else:
                    tool_response = await self.supervisor_tool_executor.ainvoke(
                        response
                    )
                    return {
                        "messages": [response] + tool_response,
                        "next": "Aki",
                        "current_agent": "Aki",
                    }

        # If no tool was used
        return {
            "messages": [AIMessage(content=self.normalize_response(response))],
            "next": "__end__",
            "current_agent": None,
        }

    async def developer_node(
        self, state: AkiTeamState, config: RunnableConfig
    ) -> AkiTeamState:
        """Developer node."""
        logging.debug("Entering developer node")
        logging.debug(f"Developer node state: {state}")
        pprint("Akisa is working!")
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self._load_prompt("akisa_team.txt")),
                MessagesPlaceholder(variable_name="akisa_messages"),
            ]
        )
        chain: Runnable = prompt | self.akisa_llm
        response = await chain.ainvoke(state, config=config)
        logging.debug(f"Developer node response: {response}")

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_response = await self.developer_tool_executor.ainvoke(response)
            return {
                "akisa_messages": [response] + tool_response,
                "next": "Akisa",
                "current_agent": "Akisa",
            }

        return {
            "messages": [HumanMessage(content=self.normalize_response(response))],
            "akisa_messages": [response],
            "next": "Aki",  # Always report back to Aki
            "current_agent": "Akisa",  # Maintain current agent while working
        }

    async def researcher_node(
        self, state: AkiTeamState, config: RunnableConfig
    ) -> AkiTeamState:
        """Researcher node."""
        logging.debug("Entering researcher node")
        logging.debug(f"Researcher node state: {state}")
        pprint("Akira is working!")
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self._load_prompt("akira_team.txt")),
                MessagesPlaceholder(variable_name="akira_messages"),
            ]
        )
        chain: Runnable = prompt | self.akira_llm
        response = await chain.ainvoke(state, config=config)
        logging.debug(f"Researcher node response: {response}")

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_response = await self.researcher_tool_executor.ainvoke(response)
            return {
                "akira_messages": [response] + tool_response,
                "next": "Akira",
                "current_agent": "Akira",
            }

        return {
            "messages": [HumanMessage(content=self.normalize_response(response))],
            "akira_messages": [response],
            "next": "Aki",  # Always report back to Aki
            "current_agent": "Akira",  # Maintain current agent while working
        }

    async def tester_node(
        self, state: AkiTeamState, config: RunnableConfig
    ) -> AkiTeamState:
        """Tester node specialized in writing and running tests."""
        logging.debug("Entering tester node")
        logging.debug(f"Tester node state: {state}")
        pprint("Akita is working!")
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self._load_prompt("akita_team.txt")),
                MessagesPlaceholder(variable_name="akita_messages"),
            ]
        )
        chain: Runnable = prompt | self.akita_llm
        response = await chain.ainvoke(state, config=config)
        logging.debug(f"Tester node response: {response}")

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_response = await self.tester_tool_executor.ainvoke(response)
            return {
                "akita_messages": [response] + tool_response,
                "next": "Akita",
                "current_agent": "Akita",
            }

        return {
            "messages": [HumanMessage(content=response.content)],
            "akita_messages": [response],
            "next": "Aki",  # Always report back to Aki
            "current_agent": "Akita",  # Maintain current agent while working
        }

    def create_graph(self):
        """Create the workflow graph using SupervisorGraph."""
        return self.graph_handler.create_graph()

    def create_default_state(self) -> AkiTeamState:
        """Create the default state for the workflow."""
        return {
            "name": self.name(),
            "messages": [],
            "next": "Aki",
            "current_agent": None,
            "aki_model": DEFAULT_MODEL,
            "akisa_model": DEFAULT_MODEL,
            "akira_model": DEFAULT_MODEL,
            "akita_model": DEFAULT_MODEL,
            "workspace_dir": os.getcwd(),
        }

    @classmethod
    def name(cls) -> str:
        return "Aki team - Chat with professionals"

    @classmethod
    def chat_profile(cls) -> cl.ChatProfile:
        return cl.ChatProfile(
            name=cls.name(),
            markdown_description="Aki supervises a team to work for you.",
            starters=[
                cl.Starter(
                    label="Introduce Aki team members",
                    message="Introduce Aki team members",
                    icon="https://cdn2.iconfinder.com/data/icons/leto-teamwork/64/__friends_team_building-128.png",
                ),
                cl.Starter(
                    label="Create a game",
                    message="Create a snake game",
                    icon="https://cdn4.iconfinder.com/data/icons/materia-color-video-games/24/003_041_game_controller_joystick_device-128.png",
                ),
                cl.Starter(
                    label="Learning new stuff",
                    message="Show a test driven use case to me, follow recent best practice",
                    icon="https://cdn1.iconfinder.com/data/icons/work-from-home-25/512/WorkFromHome_working-cat-computer-work_from_home-128.png",
                ),
            ],
        )

    @property
    def chat_settings(self) -> cl.ChatSettings:
        """Configure chat settings with model selection."""
        return cl.ChatSettings(
            [
                Select(
                    id="aki_model",
                    label="Aki Model",
                    values=sorted(
                        llm_factory.list_models(capabilities=self.capabilities)
                    ),
                    initial_index=2,
                ),
                Select(
                    id="akisa_model",
                    label="Akisa Model",
                    values=sorted(
                        llm_factory.list_models(capabilities=self.capabilities)
                    ),
                    initial_index=2,
                ),
                Select(
                    id="akira_model",
                    label="Akira Model",
                    values=sorted(
                        llm_factory.list_models(capabilities=self.capabilities)
                    ),
                    initial_index=2,
                ),
                Select(
                    id="akita_model",
                    label="Akita Model",
                    values=sorted(
                        llm_factory.list_models(capabilities=self.capabilities)
                    ),
                    initial_index=2,
                ),
            ]
        )

    def _handle_router_execution(self, response, tool_args) -> AkiTeamState:
        """Handle router tool execution and state updates."""
        next_agent = tool_args.get("next", "")
        instruction = tool_args.get("instruction", "")

        # Get valid agents from AkiTeamState type annotation
        valid_agents = AkiTeamState.__annotations__["next"].__args__

        # Normalize the agent name by matching against valid options
        input_agent = next_agent.lower()
        for agent in valid_agents:
            if agent.lower() == input_agent:
                next_agent = agent
                break

        logging.info(f"next_agent: {next_agent} with instruction: {instruction}")

        # Ensure content is properly structured
        content_text = ""
        if hasattr(response, "content") and response.content is not None:
            if isinstance(response.content, list) and len(response.content) > 0:
                first_content = response.content[0]
                if isinstance(first_content, dict) and "text" in first_content:
                    content_text = first_content["text"]
                else:
                    content_text = str(first_content)
            else:
                content_text = str(response.content)

        return_state = {
            "messages": [AIMessage(content=content_text)],
            f"{next_agent.lower()}_messages": [HumanMessage(content=instruction)],
            "next": next_agent,
            "current_agent": next_agent if next_agent != "__end__" else None,
        }

        logging.debug(f"Return state: {return_state}")
        return return_state
