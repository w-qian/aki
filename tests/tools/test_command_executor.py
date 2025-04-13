import os
from unittest.mock import patch
from aki.tools.command_executor import ShellCommandTool


def test_get_user_shell_with_shell_env():
    """Test that the tool uses the user's shell from environment."""
    tool = ShellCommandTool()
    with patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"}):
        assert tool._get_user_shell() == "/usr/bin/zsh"


def test_get_user_shell_without_shell_env():
    """Test that the tool falls back to /bin/sh when SHELL is not set."""
    tool = ShellCommandTool()
    with patch.dict(os.environ, clear=True):
        assert tool._get_user_shell() == "/bin/sh"


def test_command_uses_user_shell():
    """Test that commands are executed using the user's shell."""
    tool = ShellCommandTool()
    with (
        patch("subprocess.run") as mock_run,
        patch.dict(os.environ, {"SHELL": "/custom/shell"}),
    ):
        tool._run("test_command")

        # Verify subprocess.run was called with correct shell
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["/custom/shell", "-c", "test_command"]
        assert mock_run.call_args[1]["shell"] is False  # Using explicit shell command
