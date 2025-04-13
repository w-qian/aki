"""Installation manager implementation."""

import logging
import os
import subprocess
import sys
import platform
from pathlib import Path
from string import Template
from typing import Dict, List, Any, Optional, Union

from ....config.paths import get_aki_home

logger = logging.getLogger(__name__)


def get_platform_info():
    """Get current platform information for script selection.

    Returns:
        dict: Platform information including os_type, os_version, and architecture
    """
    return {
        "os_type": platform.system().lower(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "platform": sys.platform,
    }


def get_scripts_dir() -> Path:
    """Get the directory for installation scripts.

    Returns:
        Path: Path to the installation scripts directory
    """
    # Calculate relative to this file's location
    base_dir = Path(__file__).parent
    scripts_dir = base_dir / "scripts"
    return scripts_dir


class InstallationManager:
    """Simple installation manager for MCP servers."""

    def __init__(
        self,
        name: str,
        check_install_script: Optional[Dict[str, Any]] = None,
        install_scripts: Optional[List[Union[Dict[str, Any], str]]] = None,
    ):
        """Initialize installation manager.

        Args:
            name: Server name
            check_install_script: Optional script to check installation with command, args, and expected_output.
                                  Can also be a string path to a script file.
            install_scripts: Optional list of installation scripts or script file paths
        """
        self.name = name
        self.check_script = (
            check_install_script  # Store internally as check_script for brevity
        )
        self.install_scripts = install_scripts or []

        # Get platform information for script selection
        self.platform_info = get_platform_info()
        logger.debug(f"Platform info: {self.platform_info}")

    def check_installation(self) -> bool:
        """Check if server is installed using check_install_script if provided.

        The check script can specify:
        - command and args: The command to run
        - expected_output: String that should appear in the command output
        - expected_status: Expected return code (defaults to 0)
        - script_file: Path to a script file to execute (can be absolute or relative to scripts directory)

        Returns:
            bool: True if installed or no check needed, False if check fails
        """
        if not self.check_script:
            logger.debug(f"No check script for '{self.name}', assuming installed")
            return True

        logger.debug(f"Checking if MCP server '{self.name}' is already installed...")

        try:
            # Handle script file case
            if isinstance(self.check_script, str):
                return self._run_script_file(self.check_script, check_mode=True)
            elif isinstance(self.check_script, dict) and self.check_script.get(
                "script_file"
            ):
                script_file = self._substitute_variables(
                    self.check_script["script_file"]
                )
                return self._run_script_file(script_file, check_mode=True)

            # Handle traditional command/args case
            command = self._substitute_variables(self.check_script["command"])
            args = [
                self._substitute_variables(arg)
                for arg in self.check_script.get("args", [])
            ]

            logger.debug(f"Running installation check for '{self.name}':")
            logger.debug(f"  Command: {command}")
            logger.debug(f"  Args: {args}")

            result = subprocess.run([command] + args, capture_output=True, text=True)

            # Check for expected output if specified
            if "expected_output" in self.check_script:
                expected_raw = self.check_script["expected_output"]
                expected = self._substitute_variables(
                    expected_raw
                )  # Apply substitution here
                if expected not in result.stdout:
                    logger.debug(
                        f"Expected output '{expected}' not found in:\n{result.stdout}"
                    )
                    return False

            # Check return code
            expected_status = self.check_script.get("expected_status", 0)
            if result.returncode != expected_status:
                logger.debug(
                    f"Command returned {result.returncode}, expected {expected_status}"
                )
                if result.stderr:
                    logger.debug(f"Command error output:\n{result.stderr}")
                return False

            logger.debug("Installation check passed")
            return True

        except Exception as e:
            logger.error(f"Installation check failed for '{self.name}': {e}")
            return False

    def _run_script_file(self, script_path: str, check_mode: bool = False) -> bool:
        """Run a script file for installation or check.

        Args:
            script_path: Path to the script file
            check_mode: Whether this is a check script (return code determines success)

        Returns:
            bool: True if script succeeded, False otherwise
        """
        try:
            # Apply variable substitution to script path first
            script_path = self._substitute_variables(script_path)

            # Resolve script path (could be absolute or relative to scripts dir)
            script_file = Path(script_path)
            if not script_file.is_absolute():
                script_file = get_scripts_dir() / script_path

            if not script_file.exists():
                logger.error(f"Script file not found: {script_file}")
                return False

            # Make sure script is executable
            if not os.access(script_file, os.X_OK):
                logger.debug(f"Making script executable: {script_file}")
                script_file.chmod(script_file.stat().st_mode | 0o755)

            # Build environment with platform info and other variables
            env = os.environ.copy()

            # Get variable values
            aki_home = str(get_aki_home())
            username = os.environ.get("USER") or os.getlogin()

            env.update(
                {
                    "MCP_SERVER_NAME": self.name,
                    "MCP_OS_TYPE": self.platform_info["os_type"],
                    "MCP_OS_PLATFORM": self.platform_info["platform"],
                    "MCP_ARCHITECTURE": self.platform_info["architecture"],
                    "MCP_CHECK_MODE": "1" if check_mode else "0",
                    "AKI_HOME": aki_home,
                    "WHOAMI": username,
                }
            )

            logger.debug(f"Running script file: {script_file}")
            logger.debug(f"Environment variables for script: {env}")

            # Increased timeout to give scripts more time to complete
            logger.debug(f"Executing script: {script_file}")
            try:
                result = subprocess.run(
                    [str(script_file)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=150,  # 150 seconds timeout for installation
                )

                # Always log stdout and stderr, regardless of status
                logger.debug(f"Script stdout:\n{result.stdout}")
                if result.stderr.strip():
                    logger.debug(f"Script stderr:\n{result.stderr}")

                if result.returncode != 0:
                    logger.error(f"Script failed with return code {result.returncode}")
                    if result.stderr.strip():
                        logger.error(f"Script stderr:\n{result.stderr}")
                    # Make sure to log the script name for easier debugging
                    logger.error(f"Failed script: {script_file}")
                    return False

                return True
            except subprocess.TimeoutExpired as e:
                logger.error(
                    f"Script execution timed out after 150 seconds: {script_file}"
                )
                # Include any output that was captured before the timeout
                if e.stdout:
                    logger.error(f"Partial stdout before timeout:\n{e.stdout}")
                if e.stderr:
                    logger.error(f"Partial stderr before timeout:\n{e.stderr}")
                return False
        except Exception as e:
            logger.error(f"Failed to run script file: {e}")
            return False

    def install(self) -> bool:
        """Run installation scripts.

        Returns:
            bool: True if installation succeeded, False otherwise
        """
        if not self.install_scripts:
            logger.warning(f"No installation scripts for '{self.name}'")
            return False

        logger.info(f"Installing server '{self.name}'")

        try:
            for i, script in enumerate(self.install_scripts, 1):
                # Log installation step
                logger.info(
                    f"Running installation step {i}/{len(self.install_scripts)}"
                )

                # Handle script file case
                if isinstance(script, str):
                    success = self._run_script_file(script)
                    if not success:
                        logger.error(f"Installation script file failed: {script}")
                        return False
                    continue

                # Handle script_file key in dict
                if isinstance(script, dict) and script.get("script_file"):
                    script_file = self._substitute_variables(script["script_file"])
                    success = self._run_script_file(script_file)
                    if not success:
                        logger.error(f"Installation script file failed: {script_file}")
                        return False
                    continue

                # Handle traditional command/args case
                command = self._substitute_variables(script["command"])
                args = [
                    self._substitute_variables(arg) for arg in script.get("args", [])
                ]
                cwd = self._substitute_variables(script.get("cwd"))

                # Log command details
                logger.info(f"  Command: {command}")
                logger.info(f"  Args: {args}")
                if cwd:
                    logger.info(f"  Working Directory: {cwd}")

                # Create working directory if needed
                if cwd:
                    os.makedirs(cwd, exist_ok=True)

                try:
                    result = subprocess.run(
                        [command] + args,
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    if result.stdout:
                        logger.debug(f"Step {i} stdout:\n{result.stdout}")

                except subprocess.CalledProcessError as e:
                    logger.error(f"Installation step {i} failed:")
                    logger.error(f"  Exit Code: {e.returncode}")
                    logger.error(f"  Error Output: {e.stderr}")
                    if e.stdout:
                        logger.error(f"  Standard Output: {e.stdout}")
                    return False

            # Verify installation after all steps
            if self.check_installation():
                logger.info(f"Successfully installed server '{self.name}'")
                return True
            else:
                logger.error(
                    f"Installation completed but verification failed for '{self.name}'"
                )
                return False

        except Exception as e:
            logger.error(f"Error during installation: {str(e)}")
            return False

    def _substitute_variables(self, value: Any) -> Any:
        """Substitute variables in strings."""
        if not isinstance(value, str):
            return value

        # Get variable values
        aki_home = str(get_aki_home())
        username = os.environ.get("USER") or os.getlogin()

        # Create template variables dictionary
        variables = {
            "aki_home": aki_home,
            "whoami": username,
            # Add more variables as needed
        }

        # Use string.Template for variable substitution
        template = Template(value)
        return template.safe_substitute(variables)
