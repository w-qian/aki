"""
Process Management Tool for long-running commands.

This tool enables the management of long-running processes with the ability to:
1. Start processes in the background
2. Capture initial output for immediate feedback
3. Check process status
4. Stream additional output from running processes
5. Terminate processes when needed

Particularly useful for:
- Starting servers that don't terminate on their own
- Running development environments
- Executing commands that produce continuous output
- Testing applications that require a running server
"""

import asyncio
import concurrent.futures
import logging
import os
import signal
from typing import Dict, List, Optional, Any
from datetime import datetime

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

# Try to import psutil, but make it optional
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logging.warning(
        "psutil not installed. Some process management features will be limited."
    )

# Configure logging
logger = logging.getLogger(__name__)


class ProcessInfo:
    """Store information about a managed process."""

    def __init__(self, process, command: str):
        """Initialize process info."""
        self.process = process
        self.pid = process.pid
        self.command = command
        self.start_time = datetime.now()
        self.output_buffer = []
        self.error_buffer = []
        self.output_position = 0
        self.error_position = 0
        self.exit_code = None


class ProcessManagerInput(BaseModel):
    """Input schema for the process manager tool."""

    action: str = Field(
        description="Action to perform: 'start', 'check', 'output', 'terminate'"
    )

    command: Optional[str] = Field(
        default=None, description="Command to execute (required for 'start' action)"
    )

    process_id: Optional[int] = Field(
        default=None,
        description="Process ID (required for 'check', 'output', and 'terminate' actions)",
    )

    wait_time: Optional[int] = Field(
        default=10,
        description="Time to wait for initial output in seconds (for 'start' action, default: 10)",
    )

    max_lines: Optional[int] = Field(
        default=50,
        description="Maximum number of output lines to return (for 'output' action, default: 50)",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        """Validate the action value."""
        valid_actions = ["start", "check", "output", "terminate"]
        if v not in valid_actions:
            raise ValueError(f"Action must be one of: {', '.join(valid_actions)}")
        return v

    @field_validator("command")
    @classmethod
    def validate_command(cls, v, info):
        """Validate command is provided for 'start' action."""
        if info.data.get("action") == "start" and not v:
            raise ValueError("Command is required for 'start' action")
        return v

    @field_validator("process_id")
    @classmethod
    def validate_process_id(cls, v, info):
        """Validate process_id is provided for actions that require it."""
        if info.data.get("action") in ["check", "output", "terminate"] and v is None:
            raise ValueError(
                f"Process ID is required for '{info.data.get('action')}' action"
            )
        return v


class ProcessManagerTool(BaseTool):
    """
    Tool for managing long-running processes.

    This tool allows you to start commands in the background, monitor their output,
    check their status, and terminate them when needed. It's particularly useful for:

    1. Starting servers or development environments that run continuously
    2. Executing commands that produce ongoing output
    3. Testing applications that require a running server
    4. Managing background processes during complex workflows

    Usage examples:

    - Start a server and capture initial output:
      process_manager start "brazil-build run server" wait_time=10

    - Check if a process is still running:
      process_manager check process_id=12345

    - Get the latest output from a running process:
      process_manager output process_id=12345 max_lines=100

    - Terminate a process when done:
      process_manager terminate process_id=12345
    """

    name: str = "process_manager"
    description: str = """
    Manage long-running processes (start, check status, get output, terminate).
    
    Use this tool when you need to:
    - Start servers or services that don't terminate on their own
    - Run development environments in the background
    - Monitor command output over time
    - Clean up processes after testing
    
    The tool supports four actions:
    1. 'start': Launch a command in background and get initial output
    2. 'check': Check if a process is still running
    3. 'output': Get the latest output from a running process
    4. 'terminate': End a running process
    
    For 'start', you can specify how long to wait for initial output.
    For 'output', you can specify how many lines to retrieve.
    """

    args_schema: type[BaseModel] = ProcessManagerInput

    # Dictionary to store running processes
    _processes: Dict[int, ProcessInfo] = {}

    def _run(
        self,
        action: str,
        command: Optional[str] = None,
        process_id: Optional[int] = None,
        wait_time: int = 10,
        max_lines: int = 50,
    ) -> Dict[str, Any]:
        """
        Run the process manager tool synchronously.

        Args:
            action: Action to perform ('start', 'check', 'output', 'terminate')
            command: Command to execute (for 'start')
            process_id: Process ID (for 'check', 'output', 'terminate')
            wait_time: Time to wait for initial output in seconds (for 'start')
            max_lines: Maximum number of output lines to return (for 'output')

        Returns:
            Dictionary with action results
        """
        # Check if we're in an event loop already
        try:
            loop = asyncio.get_running_loop()
            # We're in an event loop, so we need to use a different approach
            if action == "check" or action == "terminate":
                # These can be handled synchronously
                if action == "check":
                    return self._check_process(process_id)
                else:  # terminate
                    return self._terminate_process(process_id)
            else:
                # For start and output, which are async-only, create a future
                coro = self._arun(action, command, process_id, wait_time, max_lines)
                # Use run_coroutine_threadsafe if we're in a different thread
                try:
                    future = asyncio.run_coroutine_threadsafe(coro, loop)
                    return future.result(
                        timeout=wait_time + 5
                    )  # Add a small buffer to the timeout
                except concurrent.futures.TimeoutError:
                    return {
                        "success": False,
                        "error": f"Operation timed out after {wait_time + 5} seconds",
                    }
        except RuntimeError:
            # No event loop running, we can use asyncio.run
            return asyncio.run(
                self._arun(
                    action=action,
                    command=command,
                    process_id=process_id,
                    wait_time=wait_time,
                    max_lines=max_lines,
                )
            )

    async def _arun(
        self,
        action: str,
        command: Optional[str] = None,
        process_id: Optional[int] = None,
        wait_time: int = 10,
        max_lines: int = 50,
    ) -> Dict[str, Any]:
        """
        Run the process manager tool asynchronously.

        Args:
            action: Action to perform ('start', 'check', 'output', 'terminate')
            command: Command to execute (for 'start')
            process_id: Process ID (for 'check', 'output', 'terminate')
            wait_time: Time to wait for initial output in seconds (for 'start')
            max_lines: Maximum number of output lines to return (for 'output')

        Returns:
            Dictionary with action results
        """
        try:
            if action == "start":
                return await self._start_process(command, wait_time)
            elif action == "check":
                return self._check_process(process_id)
            elif action == "output":
                return await self._get_process_output(process_id, max_lines)
            elif action == "terminate":
                return await self._terminate_process_async(process_id)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            logger.error(f"Error in process manager: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Process manager error: {str(e)}"}

    async def _start_process(self, command: str, wait_time: int) -> Dict[str, Any]:
        """
        Start a new process and capture its initial output.

        Args:
            command: Command to execute
            wait_time: Time to wait for initial output in seconds

        Returns:
            Dictionary with process info and initial output
        """
        logger.info(f"Starting process: {command}")

        try:
            # Split the command into parts if it's not already a list
            if isinstance(command, str):
                # Get user's shell
                user_shell = os.environ.get("SHELL", "/bin/sh")
                cmd_parts = [user_shell, "-c", command]
            else:
                cmd_parts = command

            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy(),
            )

            # Create process info object
            process_info = ProcessInfo(process, command)
            self._processes[process.pid] = process_info

            # Wait for initial output
            initial_output = []
            initial_errors = []

            # Set up tasks to read stdout and stderr concurrently
            stdout_task = asyncio.create_task(
                self._read_stream(process.stdout, initial_output)
            )
            stderr_task = asyncio.create_task(
                self._read_stream(process.stderr, initial_errors)
            )

            # Wait for the specified time or until the process completes
            try:
                # Wait for either the process to complete or the timeout
                done, pending = await asyncio.wait(
                    [asyncio.create_task(process.wait()), stdout_task, stderr_task],
                    timeout=wait_time,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

                # Check if the process completed
                if process.returncode is not None:
                    process_info.exit_code = process.returncode
                    status = "completed"
                else:
                    status = "running"

                # Store captured output in the process info
                process_info.output_buffer = initial_output.copy()
                process_info.error_buffer = initial_errors.copy()

            except asyncio.TimeoutError:
                # Process is still running after timeout
                status = "running"

            # Format the output for return
            combined_output = []
            line_count = 0

            # Interleave stdout and stderr based on order of appearance
            stdout_index = 0
            stderr_index = 0

            while stdout_index < len(initial_output) or stderr_index < len(
                initial_errors
            ):
                if stdout_index < len(initial_output):
                    combined_output.append(f"[stdout] {initial_output[stdout_index]}")
                    stdout_index += 1

                if stderr_index < len(initial_errors):
                    combined_output.append(f"[stderr] {initial_errors[stderr_index]}")
                    stderr_index += 1

                line_count += 1
                if line_count >= 100:  # Limit to 100 lines
                    combined_output.append("[Output truncated...]")
                    break

            # Prepare the result
            result = {
                "success": True,
                "process_id": process.pid,
                "command": command,
                "status": status,
                "initial_output": combined_output,
                "message": f"Process started with PID {process.pid}",
            }

            if process.returncode is not None:
                result["exit_code"] = process.returncode

            return result

        except Exception as e:
            logger.error(f"Error starting process: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Failed to start process: {str(e)}"}

    async def _read_stream(self, stream, buffer: List[str]) -> None:
        """
        Read from a stream and append lines to a buffer.

        Args:
            stream: The stream to read from
            buffer: List to append lines to
        """
        while True:
            line = await stream.readline()
            if not line:
                break

            line_str = line.decode("utf-8", errors="replace").rstrip()
            buffer.append(line_str)

    def _check_process(self, process_id: int) -> Dict[str, Any]:
        """
        Check if a process is still running.

        Args:
            process_id: Process ID to check

        Returns:
            Dictionary with process status
        """
        logger.info(f"Checking process: {process_id}")

        # First check our internal tracking
        if process_id in self._processes:
            process_info = self._processes[process_id]
            process = process_info.process

            # For asyncio.Process objects, returncode is updated automatically
            # We don't need to poll it manually
            if process.returncode is not None:
                process_info.exit_code = process.returncode

            # Prepare result based on process state
            if process.returncode is None:
                runtime = datetime.now() - process_info.start_time
                return {
                    "success": True,
                    "process_id": process_id,
                    "status": "running",
                    "command": process_info.command,
                    "runtime_seconds": runtime.total_seconds(),
                    "message": f"Process {process_id} is still running",
                }
            else:
                return {
                    "success": True,
                    "process_id": process_id,
                    "status": "completed",
                    "exit_code": process.returncode,
                    "command": process_info.command,
                    "message": f"Process {process_id} has completed with exit code {process.returncode}",
                }

        # If not in our tracking, check system-wide if psutil is available
        if HAS_PSUTIL:
            try:
                # Check if process exists in the system
                if psutil.pid_exists(process_id):
                    try:
                        p = psutil.Process(process_id)
                        return {
                            "success": True,
                            "process_id": process_id,
                            "status": "running",
                            "command": " ".join(p.cmdline()),
                            "message": f"Process {process_id} is running but not managed by this tool",
                        }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        return {
                            "success": True,
                            "process_id": process_id,
                            "status": "inaccessible",
                            "message": f"Process {process_id} exists but cannot be accessed",
                        }
                else:
                    return {
                        "success": True,
                        "process_id": process_id,
                        "status": "not_found",
                        "message": f"No process with ID {process_id} was found",
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error checking process {process_id}: {str(e)}",
                }
        else:
            # Limited functionality without psutil
            return {
                "success": False,
                "error": f"Process {process_id} not found in managed processes. Install psutil for enhanced process checking.",
            }

    async def _get_process_output(
        self, process_id: int, max_lines: int
    ) -> Dict[str, Any]:
        """
        Get the latest output from a process.

        Args:
            process_id: Process ID
            max_lines: Maximum number of output lines to return

        Returns:
            Dictionary with process output
        """
        logger.info(f"Getting output for process: {process_id}")

        if process_id not in self._processes:
            return {
                "success": False,
                "error": f"Process {process_id} is not managed by this tool",
            }

        process_info = self._processes[process_id]
        process = process_info.process

        # Check if the process is still running
        if process.returncode is None:
            # Process is still running, try to get new output
            stdout_buffer = []
            stderr_buffer = []

            # Read available output without blocking
            try:
                stdout_task = asyncio.create_task(
                    self._read_stream(process.stdout, stdout_buffer)
                )
                stderr_task = asyncio.create_task(
                    self._read_stream(process.stderr, stderr_buffer)
                )

                # Wait for a short time to collect output
                await asyncio.wait([stdout_task, stderr_task], timeout=0.5)

                # Cancel tasks if they're still running
                if not stdout_task.done():
                    stdout_task.cancel()
                if not stderr_task.done():
                    stderr_task.cancel()

                # Append new output to buffers
                process_info.output_buffer.extend(stdout_buffer)
                process_info.error_buffer.extend(stderr_buffer)

            except Exception as e:
                logger.error(f"Error reading process output: {str(e)}", exc_info=True)

        # Prepare output for return
        combined_output = []

        # Get the most recent output lines
        stdout_lines = (
            process_info.output_buffer[-max_lines:]
            if process_info.output_buffer
            else []
        )
        stderr_lines = (
            process_info.error_buffer[-max_lines:] if process_info.error_buffer else []
        )

        # Interleave stdout and stderr
        stdout_index = 0
        stderr_index = 0

        while stdout_index < len(stdout_lines) or stderr_index < len(stderr_lines):
            if stdout_index < len(stdout_lines):
                combined_output.append(f"[stdout] {stdout_lines[stdout_index]}")
                stdout_index += 1

            if stderr_index < len(stderr_lines):
                combined_output.append(f"[stderr] {stderr_lines[stderr_index]}")
                stderr_index += 1

        # Prepare result
        result = {
            "success": True,
            "process_id": process_id,
            "command": process_info.command,
            "output": combined_output,
            "output_lines": len(combined_output),
            "total_stdout_lines": len(process_info.output_buffer),
            "total_stderr_lines": len(process_info.error_buffer),
        }

        # Add status information
        if process.returncode is None:
            result["status"] = "running"
            runtime = datetime.now() - process_info.start_time
            result["runtime_seconds"] = runtime.total_seconds()
        else:
            result["status"] = "completed"
            result["exit_code"] = process.returncode

        return result

    async def _terminate_process_async(self, process_id: int) -> Dict[str, Any]:
        """
        Terminate a running process asynchronously.

        Args:
            process_id: Process ID to terminate

        Returns:
            Dictionary with termination result
        """
        logger.info(f"Terminating process: {process_id}")

        if process_id not in self._processes:
            # Check if the process exists in the system (if psutil is available)
            if HAS_PSUTIL and psutil.pid_exists(process_id):
                try:
                    # Attempt to terminate the process even if not managed by us
                    os.kill(process_id, signal.SIGTERM)
                    return {
                        "success": True,
                        "process_id": process_id,
                        "status": "terminated",
                        "message": f"Process {process_id} terminated (was not managed by this tool)",
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to terminate process {process_id}: {str(e)}",
                    }
            else:
                # Try basic termination without psutil
                try:
                    os.kill(process_id, signal.SIGTERM)
                    return {
                        "success": True,
                        "process_id": process_id,
                        "status": "terminated",
                        "message": f"Process {process_id} terminated (was not managed by this tool)",
                    }
                except ProcessLookupError:
                    return {
                        "success": False,
                        "error": f"Process {process_id} not found",
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to terminate process {process_id}: {str(e)}",
                    }

        process_info = self._processes[process_id]
        process = process_info.process

        # Check if the process is already completed
        if process.returncode is not None:
            return {
                "success": True,
                "process_id": process_id,
                "status": "already_completed",
                "exit_code": process.returncode,
                "message": f"Process {process_id} already completed with exit code {process.returncode}",
            }

        try:
            # Try to terminate gracefully first
            process.terminate()

            # Wait a bit for the process to terminate
            try:
                exit_code = await asyncio.wait_for(process.wait(), 5.0)
                self._processes[process_id].exit_code = exit_code

                return {
                    "success": True,
                    "process_id": process_id,
                    "status": "terminated",
                    "exit_code": exit_code,
                    "message": f"Process {process_id} terminated with exit code {exit_code}",
                }
            except asyncio.TimeoutError:
                # Process didn't terminate gracefully, force kill
                process.kill()

                try:
                    exit_code = await asyncio.wait_for(process.wait(), 5.0)
                    self._processes[process_id].exit_code = exit_code

                    return {
                        "success": True,
                        "process_id": process_id,
                        "status": "killed",
                        "exit_code": exit_code,
                        "message": f"Process {process_id} forcefully killed with exit code {exit_code}",
                    }
                except asyncio.TimeoutError:
                    return {
                        "success": False,
                        "error": f"Failed to kill process {process_id} after multiple attempts",
                    }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error terminating process {process_id}: {str(e)}",
            }

    def _terminate_process(self, process_id: int) -> Dict[str, Any]:
        """
        Synchronous wrapper for process termination.

        Args:
            process_id: Process ID to terminate

        Returns:
            Dictionary with termination result
        """
        if process_id not in self._processes:
            # For external processes, we can use the synchronous method
            if HAS_PSUTIL and psutil.pid_exists(process_id):
                try:
                    os.kill(process_id, signal.SIGTERM)
                    return {
                        "success": True,
                        "process_id": process_id,
                        "status": "terminated",
                        "message": f"Process {process_id} terminated (was not managed by this tool)",
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to terminate process {process_id}: {str(e)}",
                    }
            else:
                try:
                    os.kill(process_id, signal.SIGTERM)
                    return {
                        "success": True,
                        "process_id": process_id,
                        "status": "terminated",
                        "message": f"Process {process_id} terminated (was not managed by this tool)",
                    }
                except ProcessLookupError:
                    return {
                        "success": False,
                        "error": f"Process {process_id} not found",
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to terminate process {process_id}: {str(e)}",
                    }

        process_info = self._processes[process_id]
        process = process_info.process

        # Check if the process is already completed
        if process.returncode is not None:
            return {
                "success": True,
                "process_id": process_id,
                "status": "already_completed",
                "exit_code": process.returncode,
                "message": f"Process {process_id} already completed with exit code {process.returncode}",
            }

        # For asyncio.Process objects, we need to run the async version in a new event loop
        try:
            # Create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the async termination
            result = loop.run_until_complete(self._terminate_process_async(process_id))

            # Clean up
            loop.close()

            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error terminating process {process_id}: {str(e)}",
            }


def create_process_manager_tool() -> ProcessManagerTool:
    """
    Create and return a process manager tool.

    Returns:
        A ProcessManagerTool instance
    """
    return ProcessManagerTool()
