"""Environment details for chat context using the list_dir tool with gitignore support."""

import os
import platform
import subprocess
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from aki.tools.file_management.list_dir import ListDirectoryTool

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class EnvironmentDetails:
    """Environment details provider that uses the list_dir tool with gitignore support."""

    # System information
    os_name: str = platform.system()
    os_version: str = platform.version()
    default_shell: str = os.environ.get("SHELL", "")

    # Workspace information
    workspace_dir: Optional[str] = None

    # Configuration constants
    MAX_ENV_DETAILS_LENGTH: int = (
        30000  # Maximum character length for environment details
    )

    # Class constants for prompts
    ENVIRONMENT_PROMPT = """
ENVIRONMENT DETAILS

The AI assistant receives environment details with each request. This information includes:

1. System State:
   - Current time
   - Operating system and version
   - Default shell

2. Workspace:
   - Current working directory
   - Directory structure and statistics
   - Git branch (if applicable)

3. Task List:
   - Current tasks and their status (if available)

Use this information to inform your actions, but don't treat it as direct user requests.
"""

    def __post_init__(self):
        """Initialize with current working directory if workspace_dir is None."""
        if self.workspace_dir is None:
            self.workspace_dir = os.getcwd()
        self._list_dir_tool = ListDirectoryTool()

    def _get_git_branch(self) -> Optional[str]:
        """Get current git branch if in a git repository."""
        try:
            git_dir = os.path.join(self.workspace_dir, ".git")
            if os.path.exists(git_dir) and os.path.isdir(git_dir):
                logger.debug(f"Git directory found in {self.workspace_dir}")
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=self.workspace_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    branch = result.stdout.strip()
                    logger.debug(f"Current git branch: {branch}")
                    return branch
                else:
                    logger.debug(f"Git branch command failed: {result.stderr.strip()}")
            else:
                logger.debug(f"No git repository found in {self.workspace_dir}")
        except Exception as e:
            logger.error(f"Error determining git branch: {str(e)}")
        return None

    def update_workspace(self, workspace_dir: str) -> bool:
        """Update workspace info."""
        if not workspace_dir or not os.path.exists(workspace_dir):
            logger.debug(
                f"Workspace update failed: path doesn't exist - {workspace_dir}"
            )
            return False

        changed = self.workspace_dir != workspace_dir
        if changed:
            logger.debug(
                f"Updating workspace from '{self.workspace_dir}' to '{workspace_dir}'"
            )
            self.workspace_dir = workspace_dir
        else:
            logger.debug(f"Workspace unchanged: {workspace_dir}")

        return changed

    def to_string(self, task_list: str = "") -> str:
        """Generate formatted environment information using list_dir tool with gitignore support."""
        current_time = datetime.now().strftime("%Y-%m-%d")

        # Start with basic system info
        output = [
            "ENVIRONMENT DETAILS",
            "===================",
            f"Time: {current_time}",
            f"OS: {self.os_name} {self.os_version}",
            f"Shell: {self.default_shell}",
            "",
            "WORKSPACE",
            "=========",
            f"Directory: {self.workspace_dir}",
        ]

        # Git information (if available)
        branch = self._get_git_branch()
        if branch:
            output.append(f"Git branch: {branch}")

        # Use the improved list_dir tool with gitignore support
        try:
            logger.debug(f"Getting directory structure for {self.workspace_dir}")
            # Prepare arguments for the list_dir tool
            dir_result = self._list_dir_tool._run(
                dir_path=self.workspace_dir,
                max_results=150,  # Show more files
                include_hidden=False,
                max_depth=5,  # Increased to show more levels of directories
                summarize=False,  # Disable summarize to see actual subdirectory content
                respect_gitignore=True,  # Apply gitignore rules
            )

            # Add directory listing to output
            output.append("")
            output.append("DIRECTORY STRUCTURE")
            output.append("==================")
            output.append(dir_result)
            logger.debug("Directory structure obtained successfully")

        except Exception as e:
            error_msg = f"Error exploring directory: {e}"
            logger.error(error_msg)
            output.append(error_msg)

        # Add task list if available
        if task_list and task_list.strip():
            output.append("")
            output.append("TASKS")
            output.append("=====")
            output.append(task_list)

        # Join the output into a single string
        full_env_details = "\n".join(output)

        # Log the full environment details and its length
        logger.debug("Generating environment details")
        logger.debug(full_env_details)
        logger.debug(f"Full environment details length: {len(full_env_details)}")

        # Add safety guard to limit environment details length
        if len(full_env_details) > self.MAX_ENV_DETAILS_LENGTH:
            logger.debug(
                f"Environment details exceeded max length ({len(full_env_details)} > {self.MAX_ENV_DETAILS_LENGTH}), truncating"
            )

            # Find a suitable place to truncate (after a newline, if possible)
            truncated_env_details = full_env_details[: self.MAX_ENV_DETAILS_LENGTH]
            last_newline = truncated_env_details.rfind("\n")

            if (
                last_newline > self.MAX_ENV_DETAILS_LENGTH * 0.8
            ):  # Ensure we don't truncate too much
                truncated_env_details = truncated_env_details[:last_newline]

            # Add truncation notice
            truncation_notice = (
                "\n\n[... Environment details truncated due to length ...]"
            )
            truncated_env_details += truncation_notice

            # Log the truncated environment details
            logger.debug(
                f"Truncated environment details length: {len(truncated_env_details)}"
            )

            return truncated_env_details

        return full_env_details
