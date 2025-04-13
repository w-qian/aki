import chainlit as cl
import logging
import json
from typing import List, Dict
from langchain_core.messages import ToolMessage, AIMessage
from aki.tools.param_conversion import (
    identify_tools_needing_conversion,
    convert_tool_args,
)


class ToolExecutor:
    """
    An tool executor that takes an AIMessage and returns a list of ToolMessage
    """

    def __init__(self, tools: List) -> None:
        self.tools_by_name = {tool.name: tool for tool in tools}
        # Identify tools that might need parameter conversion
        self.tools_with_param_conversion = identify_tools_needing_conversion(tools)

    async def ainvoke(self, message: AIMessage) -> Dict:
        if not message.tool_calls:
            raise ValueError("No tool calls found in message")

        outputs = []
        for tool_call in message.tool_calls:
            async with cl.Step(name=f"tool [{tool_call['name']}]", type="tool") as step:
                try:
                    # Convert camelCase parameter names to snake_case if needed
                    converted_args = convert_tool_args(
                        tool_call["name"],
                        tool_call["args"],
                        self.tools_with_param_conversion,
                    )

                    # Execute the tool with converted arguments
                    tool_result = await self.tools_by_name[tool_call["name"]]._arun(
                        **converted_args
                    )
                except Exception as e:
                    # Log the exception with detailed information
                    logging.error(
                        f"Tool execution failed for {tool_call['name']}: {str(e)}",
                        exc_info=True,
                    )

                    # Create a structured error response
                    tool_result = {
                        "status": "error",
                        "message": f"Tool execution failed: {str(e)}",
                        "tool_name": tool_call["name"],
                    }

                outputs.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )
                # logging.debug(f"{tool_call['name']} \nInput: {tool_call['args']}, \nOutput: {tool_result}")
                step.input = tool_call["args"]
                step.output = tool_result

        return outputs
