"""Tests for the copy file tool."""

import pytest
import tempfile
from pathlib import Path

from aki.tools.file_management.copy import CopyFileTool


@pytest.fixture
def test_environment():
    """Create test directories and files for copy testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory structure for testing
        workspace_dir = Path(tmpdir) / "workspace"
        outside_dir = Path(tmpdir) / "outside"

        # Create the directories
        workspace_dir.mkdir()
        outside_dir.mkdir()
        (workspace_dir / "subdir").mkdir()

        # Create test files
        source_file = workspace_dir / "source_file.txt"
        source_file.write_text("This is a source file for copying")

        outside_source = outside_dir / "outside_source.txt"
        outside_source.write_text("This is a source file outside the workspace")

        # Create a tool instance
        copy_tool = CopyFileTool(root_dir=str(workspace_dir))

        yield {
            "workspace_dir": workspace_dir,
            "outside_dir": outside_dir,
            "source_file": source_file,
            "outside_source": outside_source,
            "copy_tool": copy_tool,
        }


def test_copy_file_within_workspace(test_environment):
    """Test copying a file within the workspace."""
    copy_tool = test_environment["copy_tool"]
    source_file = test_environment["source_file"]
    workspace_dir = test_environment["workspace_dir"]
    dest_file = workspace_dir / "dest_file.txt"

    result = copy_tool._run(str(source_file), str(dest_file))

    # Check result message
    assert "successfully" in result.lower()
    # Check that the file exists
    assert dest_file.exists()
    # Check that the content was copied correctly
    assert dest_file.read_text() == "This is a source file for copying"


def test_copy_file_to_subdir(test_environment):
    """Test copying a file to a subdirectory within the workspace."""
    copy_tool = test_environment["copy_tool"]
    source_file = test_environment["source_file"]
    workspace_dir = test_environment["workspace_dir"]
    dest_file = workspace_dir / "subdir" / "dest_file.txt"

    result = copy_tool._run(str(source_file), str(dest_file))

    # Check result message
    assert "successfully" in result.lower()
    # Check that the file exists
    assert dest_file.exists()
    # Check that the content was copied correctly
    assert dest_file.read_text() == "This is a source file for copying"


def test_copy_from_outside_to_workspace(test_environment):
    """Test copying a file from outside to workspace (should work)."""
    copy_tool = test_environment["copy_tool"]
    outside_source = test_environment["outside_source"]
    workspace_dir = test_environment["workspace_dir"]
    dest_file = workspace_dir / "from_outside.txt"

    result = copy_tool._run(str(outside_source), str(dest_file))

    # Check result message
    assert "successfully" in result.lower()
    # Check that the file exists
    assert dest_file.exists()
    # Check that the content was copied correctly
    assert dest_file.read_text() == "This is a source file outside the workspace"


def test_copy_to_outside_workspace(test_environment):
    """Test copying a file to outside workspace (should fail)."""
    copy_tool = test_environment["copy_tool"]
    source_file = test_environment["source_file"]
    outside_dir = test_environment["outside_dir"]
    dest_file = outside_dir / "should_not_create.txt"

    result = copy_tool._run(str(source_file), str(dest_file))

    # Check result message indicates error
    assert "error" in result.lower()
    # Check that the file was not created
    assert not dest_file.exists()


def test_copy_nonexistent_source(test_environment):
    """Test copying a nonexistent source file."""
    copy_tool = test_environment["copy_tool"]
    workspace_dir = test_environment["workspace_dir"]
    nonexistent = workspace_dir / "nonexistent.txt"
    dest_file = workspace_dir / "dest_file.txt"

    result = copy_tool._run(str(nonexistent), str(dest_file))

    # Check result message indicates error
    assert "error" in result.lower()
    # Check that the destination file was not created
    assert not dest_file.exists()
