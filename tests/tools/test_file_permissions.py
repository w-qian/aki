import json
import pytest
import tempfile
from pathlib import Path

from aki.tools.file_management.list_dir import ListDirectoryTool
from aki.tools.file_management.read import ReadFileTool
from aki.tools.file_management.write import WriteFileTool
from aki.tools.file_management.delete import DeleteFileTool


@pytest.fixture
def test_fixture():
    """Create a test fixture with controlled workspace and outside directories."""
    with tempfile.TemporaryDirectory() as tmp_root:
        # Create workspace directory
        workspace_dir = Path(tmp_root) / "workspace"
        workspace_dir.mkdir()
        workspace_file = workspace_dir / "workspace_file.txt"
        workspace_file.write_text("Content in workspace")

        # Create directory outside workspace
        outside_dir = Path(tmp_root) / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "outside_file.txt"
        outside_file.write_text("Content outside workspace")

        # Create tools with root directory set to workspace
        list_tool = ListDirectoryTool(root_dir=str(workspace_dir))
        read_tool = ReadFileTool(root_dir=str(workspace_dir))
        write_tool = WriteFileTool(root_dir=str(workspace_dir))
        delete_tool = DeleteFileTool(root_dir=str(workspace_dir))

        # Return the fixture
        yield {
            "workspace_dir": workspace_dir,
            "outside_dir": outside_dir,
            "workspace_file": workspace_file,
            "outside_file": outside_file,
            "list_tool": list_tool,
            "read_tool": read_tool,
            "write_tool": write_tool,
            "delete_tool": delete_tool,
        }


def test_read_file_in_workspace(test_fixture):
    """Test reading a file within the workspace."""
    read_tool = test_fixture["read_tool"]
    workspace_file = test_fixture["workspace_file"]

    result = json.loads(read_tool._run(file_path=str(workspace_file)))

    assert result["error"] is None
    assert result["content"] == "Content in workspace"


def test_read_file_outside_workspace(test_fixture):
    """Test reading a file outside the workspace."""
    read_tool = test_fixture["read_tool"]
    outside_file = test_fixture["outside_file"]

    # Reading outside workspace should be allowed
    result = json.loads(read_tool._run(file_path=str(outside_file)))

    # Should succeed since reading outside workspace is allowed
    assert result["error"] is None
    assert result["content"] == "Content outside workspace"


def test_write_file_in_workspace(test_fixture):
    """Test writing a file within the workspace."""
    write_tool = test_fixture["write_tool"]
    new_file = test_fixture["workspace_dir"] / "new_file.txt"

    result = json.loads(write_tool._run(file_path=str(new_file), text="New content"))

    # Check the operation succeeded
    assert result["error"] is None
    assert result["success"] is True

    # Check file was actually written
    assert new_file.exists()
    assert new_file.read_text() == "New content"


def test_write_file_outside_workspace(test_fixture):
    """Test writing a file outside the workspace."""
    write_tool = test_fixture["write_tool"]
    outside_file = test_fixture["outside_file"]

    result = json.loads(
        write_tool._run(file_path=str(outside_file), text="Modified content")
    )

    # Check the operation failed (writing outside workspace not allowed)
    assert result["error"] is not None
    assert "denied" in result["error"] or "restricted" in result["error"]
    assert result["success"] is False

    # Check file wasn't modified
    assert outside_file.read_text() == "Content outside workspace"


def test_delete_file_in_workspace(test_fixture):
    """Test deleting a file within the workspace."""
    delete_tool = test_fixture["delete_tool"]
    workspace_file = test_fixture["workspace_file"]

    # First make sure file exists
    assert workspace_file.exists()

    # Delete the file
    result = delete_tool._run(file_path=str(workspace_file))

    # Check operation succeeded
    assert (
        "deleted successfully" in result.lower()
        or "successfully deleted" in result.lower()
    )

    # Check file was actually deleted
    assert not workspace_file.exists()


def test_delete_file_outside_workspace(test_fixture):
    """Test deleting a file outside the workspace."""
    delete_tool = test_fixture["delete_tool"]
    outside_file = test_fixture["outside_file"]

    # First make sure file exists
    assert outside_file.exists()

    # Try to delete the file
    result = delete_tool._run(file_path=str(outside_file))

    # Check operation failed
    assert (
        "error" in result.lower()
        or "denied" in result.lower()
        or "restricted" in result.lower()
    )

    # Check file wasn't deleted
    assert outside_file.exists()
