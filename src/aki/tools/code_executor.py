"""Code execution tools"""

import os
import logging
from typing import Optional, Type
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field
import io
import contextlib
import traceback
from logging import StreamHandler, getLogger


class ExecutePythonInput(BaseModel):
    """Input schema for ExecutePythonTool."""

    code: str = Field(description="Python code to execute")


class ExecutePythonTool(BaseTool):
    """Tool for executing Python code and returning results."""

    name: str = "execute_python"
    args_schema: Type[BaseModel] = ExecutePythonInput
    description: str = (
        "Execute python code and return any result, stdout, stderr, and error."
    )

    def _run(
        self,
        code: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the Python code synchronously."""
        logging.debug("Executing Python code")
        state = None
        try:
            import chainlit as cl

            state = cl.user_session.get("state")
            logging.debug(
                f"Got state with workspace_dir: {state.get('workspace_dir') if state else None}"
            )
        except ImportError:
            logging.warning("Chainlit not available, running without state")

        # Prepare output capture
        stdout = io.StringIO()
        stderr = io.StringIO()
        log_capture = io.StringIO()
        log_handler = StreamHandler(log_capture)
        root_logger = getLogger()

        # Get workspace directory for saving artifacts
        workspace_dir = (
            state.get("workspace_dir")
            if (state and "workspace_dir" in state)
            else os.getcwd()
        )
        artifacts_dir = os.path.join(workspace_dir, ".artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)

        try:
            # Add log handler temporarily
            root_logger.addHandler(log_handler)

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                # Create a new namespace for execution
                namespace = {
                    "__name__": "__main__",
                }

                # Execute the code
                exec(code, namespace)

            # Collect output
            output = stdout.getvalue()
            errors = stderr.getvalue()
            logs = log_capture.getvalue()

            # Format response message
            message = ""

            if output:
                message += f"Output:\n{output}\n"

            if errors:
                message += f"Stderr:\n{errors}\n"

            # Only include logs if they appear to be from the executed code
            # Filter out "Getting data layer None" messages
            relevant_logs = "\n".join(
                line
                for line in logs.splitlines()
                if "Getting data layer None" not in line
            )
            if relevant_logs.strip():
                message += f"Logs:\n{relevant_logs}\n"

            return message if message else "Code executed successfully with no output."

        except Exception:
            error_msg = f"Error executing Python code:\n{traceback.format_exc()}"
            logging.debug(error_msg)
            return error_msg
        finally:
            stdout.close()
            stderr.close()
            log_capture.close()
            root_logger.removeHandler(log_handler)

    async def _arun(
        self,
        code: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the Python code asynchronously."""
        return self._run(code=code, run_manager=run_manager)


def create_execute_python_tool() -> BaseTool:
    """Create and return the execute python tool."""
    return ExecutePythonTool()


# List of available tools
code_executor_tools = [create_execute_python_tool()]
