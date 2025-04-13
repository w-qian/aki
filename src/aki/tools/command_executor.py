import subprocess
import logging
import os
import asyncio
from typing import Dict, Any, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from .file_management.base_tools import WriteFileTool as WriteFileBase

# Error message template
INVALID_PATH_TEMPLATE = "Error: Access denied to {arg_name}: {value}. Permission granted exclusively to the current working directory"


class ShellCommandInput(BaseModel):
    """Input for shell command execution."""

    command: str = Field(description="The shell command to execute")
    working_dir: Optional[str] = Field(
        default=".", description="Working directory for command execution"
    )


class ShellCommandTool(BaseTool, WriteFileBase):
    """A tool for executing shell commands."""

    name: str = "shell_command"
    description: str = "Execute a shell command in a specified working directory"
    args_schema: type[BaseModel] = ShellCommandInput

    def _get_user_shell(self) -> str:
        """
        Get the user's default shell from environment variables.
        Falls back to /bin/sh if SHELL is not set.
        """
        return os.environ.get("SHELL", "/bin/sh")

    def _run(self, command: str, working_dir: str = ".") -> Dict[str, Any]:
        """
        Execute a shell command and return results.

        Args:
            command: The shell command to execute
            working_dir: Working directory for command execution

        Returns:
            A dictionary with command execution results
        """
        logging.debug(f"Executing shell command: {command}")
        resolved_path = self.resolve_path(working_dir)

        # Check if path resolution had errors
        if resolved_path.startswith("Error:"):
            return {"success": False, "output": None, "error": resolved_path}

        working_dir = resolved_path
        logging.debug(f"Working directory: {working_dir}")

        try:
            # Get user's shell
            user_shell = self._get_user_shell()
            logging.debug(f"Using shell: {user_shell}")

            # Create environment with explicit shell setting
            env = {**os.environ, "SHELL": user_shell}

            # Execute command through the user's shell
            result = subprocess.run(
                [user_shell, "-c", command],
                shell=False,  # We're explicitly specifying the shell, so shell=False
                cwd=working_dir,
                capture_output=True,
                text=True,
                env=env,
                timeout=300,  # 5-minute timeout
            )

            # Prepare the result dictionary
            output_dict = {
                "success": result.returncode == 0,
                "output": result.stdout.strip() if result.stdout else None,
                "error": result.stderr.strip() if result.stderr else None,
            }

            # Log the results
            if output_dict["success"]:
                logging.debug(f"Command executed successfully: {command}")
                if output_dict["output"]:
                    logging.debug(f"Command output: {output_dict['output']}")
            else:
                logging.debug(f"Command failed: {command}")
                if output_dict["error"]:
                    logging.debug(f"Command error: {output_dict['error']}")

            return output_dict

        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out: {command}"
            logging.debug(error_msg)
            return {"success": False, "output": None, "error": error_msg}
        except Exception as e:
            error_msg = f"Exception in command execution: {str(e)}"
            logging.debug(error_msg)
            return {"success": False, "output": None, "error": error_msg}

    async def _arun(self, command: str, working_dir: str = ".") -> Dict[str, Any]:
        """
        Asynchronously execute a shell command.

        Args:
            command: The shell command to execute
            working_dir: Working directory for command execution

        Returns:
            A dictionary with command execution results
        """
        logging.debug(f"Executing shell command: {command}")
        resolved_path = self.resolve_path(working_dir)

        # Check if path resolution had errors
        if resolved_path.startswith("Error:"):
            return {"success": False, "output": None, "error": resolved_path}

        working_dir = resolved_path
        logging.debug(f"Working directory: {working_dir}")

        try:
            # Get user's shell
            user_shell = self._get_user_shell()
            logging.debug(f"Using shell: {user_shell}")

            # Create environment with explicit shell setting
            env = {**os.environ, "SHELL": user_shell}

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                user_shell,
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=env,
            )

            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            # Prepare the result dictionary
            output_dict = {
                "success": process.returncode == 0,
                "output": stdout.decode().strip() if stdout else None,
                "error": stderr.decode().strip() if stderr else None,
            }

            # Log the results
            if output_dict["success"]:
                logging.debug(f"Command executed successfully: {command}")
                if output_dict["output"]:
                    logging.debug(f"Command output: {output_dict['output']}")
            else:
                logging.debug(f"Command failed: {command}")
                if output_dict["error"]:
                    logging.debug(f"Command error: {output_dict['error']}")

            return output_dict

        except asyncio.TimeoutError:
            error_msg = f"Command timed out after 60 seconds: {command}"
            logging.error(error_msg)
            return {"success": False, "output": None, "error": error_msg}
        except Exception as e:
            error_msg = f"Exception in command execution: {str(e)}"
            logging.error(error_msg)
            return {"success": False, "output": None, "error": error_msg}


def create_shell_command_tool() -> ShellCommandTool:
    """
    Create and return a shell command tool.

    Returns:
        A ShellCommandTool instance
    """
    return ShellCommandTool()
