"""Tests for the move file tool."""

import pytest
import tempfile
from pathlib import Path

from aki.tools.file_management.move import MoveFileTool


@pytest.fixture
def test_environment():
    """Create test directories and files for move testing."""
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
        source_file.write_text("This is a source file for moving")

        outside_source = outside_dir / "outside_source.txt"
        outside_source.write_text("This is a source file outside the workspace")

        # Create a tool instance
        move_tool = MoveFileTool(root_dir=str(workspace_dir))

        yield {
            "workspace_dir": workspace_dir,
            "outside_dir": outside_dir,
            "source_file": source_file,
            "outside_source": outside_source,
            "move_tool": move_tool,
        }


def test_move_file_within_workspace(test_environment):
    """Test moving a file within the workspace."""
    move_tool = test_environment["move_tool"]
    source_file = test_environment["source_file"]
    workspace_dir = test_environment["workspace_dir"]
    dest_file = workspace_dir / "moved_file.txt"

    # Confirm source exists before move
    assert source_file.exists()

    result = move_tool._run(str(source_file), str(dest_file))

    # Check result message
    assert "successfully" in result.lower()
    # Check that the source file no longer exists
    assert not source_file.exists()
    # Check that the destination file exists
    assert dest_file.exists()
    # Check that the content was moved correctly
    assert dest_file.read_text() == "This is a source file for moving"


def test_move_file_to_subdir(test_environment):
    """Test moving a file to a subdirectory within the workspace."""
    move_tool = test_environment["move_tool"]
    workspace_dir = test_environment["workspace_dir"]

    # Create a new source file for this test
    source_file = workspace_dir / "source_file_subdir.txt"
    source_file.write_text("This is a source file for subdirectory moving")

    dest_file = workspace_dir / "subdir" / "moved_file.txt"

    result = move_tool._run(str(source_file), str(dest_file))

    # Check result message
    assert "successfully" in result.lower()
    # Check that the source file no longer exists
    assert not source_file.exists()
    # Check that the destination file exists
    assert dest_file.exists()
    # Check that the content was moved correctly
    assert dest_file.read_text() == "This is a source file for subdirectory moving"


def test_move_from_outside_to_workspace(test_environment):
    """Test moving a file from outside to workspace (should work)."""
    move_tool = test_environment["move_tool"]
    outside_source = test_environment["outside_source"]
    workspace_dir = test_environment["workspace_dir"]
    dest_file = workspace_dir / "from_outside.txt"

    result = move_tool._run(str(outside_source), str(dest_file))

    # Check result message
    assert "successfully" in result.lower()
    # Check that the source file no longer exists
    assert not outside_source.exists()
    # Check that the destination file exists
    assert dest_file.exists()
    # Check that the content was moved correctly
    assert dest_file.read_text() == "This is a source file outside the workspace"


def test_move_to_outside_workspace(test_environment):
    """Test moving a file to outside workspace (should fail)."""
    move_tool = test_environment["move_tool"]
    workspace_dir = test_environment["workspace_dir"]
    outside_dir = test_environment["outside_dir"]

    # Create a new source file for this test
    source_file = workspace_dir / "source_outside_move.txt"
    source_file.write_text("This file should not be moved outside")

    dest_file = outside_dir / "should_not_create.txt"

    result = move_tool._run(str(source_file), str(dest_file))

    # Check result message indicates error
    assert "error" in result.lower()
    # Check that the source file still exists
    assert source_file.exists()
    # Check that the destination file was not created
    assert not dest_file.exists()


def test_move_nonexistent_source(test_environment):
    """Test moving a nonexistent source file."""
    move_tool = test_environment["move_tool"]
    workspace_dir = test_environment["workspace_dir"]
    nonexistent = workspace_dir / "nonexistent.txt"
    dest_file = workspace_dir / "moved_nonexistent.txt"

    result = move_tool._run(str(nonexistent), str(dest_file))

    # Check result message indicates error
    assert "error" in result.lower()
    # Check that the destination file was not created
    assert not dest_file.exists()


def test_move_rename_file(test_environment):
    """Test renaming a file (move within same directory)."""
    move_tool = test_environment["move_tool"]
    workspace_dir = test_environment["workspace_dir"]

    # Create a new source file for this test
    source_file = workspace_dir / "rename_source.txt"
    source_file.write_text("This file will be renamed")

    renamed_file = workspace_dir / "renamed_file.txt"

    result = move_tool._run(str(source_file), str(renamed_file))

    # Check result message
    assert "successfully" in result.lower()
    # Check that the source file no longer exists
    assert not source_file.exists()
    # Check that the renamed file exists
    assert renamed_file.exists()
    # Check that the content is preserved
    assert renamed_file.read_text() == "This file will be renamed"
