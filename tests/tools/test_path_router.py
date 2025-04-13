"""Legacy path router tests updated to match the new security model."""

import os
import pytest
import tempfile
from pathlib import Path

from aki.tools.file_management.file_paths import (
    FilePathResolver,
    OPERATION_READ,
    OPERATION_WRITE,
    FileNotFoundError,
    AccessDeniedError,
)
from aki.tools.file_management.base_tools import ReadFileTool, WriteFileTool
from aki.tools.file_management.whitelist import (
    WHITELISTED_PATHS,
)


@pytest.fixture
def test_home_dir():
    """Create a mock home directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home_dir = Path(tmpdir)

        # Create a mock .aki directory in the test home dir
        aki_dir = home_dir / ".aki"
        aki_dir.mkdir()

        # Create some test files
        (aki_dir / "config.json").write_text('{"test": "config"}')
        (aki_dir / "test_file.txt").write_text("Test file content")
        (home_dir / "regular_file.txt").write_text("Regular file in home")

        # Save original home dir to restore later
        original_home = os.environ.get("HOME")
        # Mock the home directory for testing
        os.environ["HOME"] = str(home_dir)

        # Add to whitelist for testing
        WHITELISTED_PATHS.add(home_dir / ".aki")

        yield home_dir

        # Cleanup
        if original_home:
            os.environ["HOME"] = original_home
        # Remove from whitelist
        if home_dir / ".aki" in WHITELISTED_PATHS:
            WHITELISTED_PATHS.remove(home_dir / ".aki")


@pytest.fixture
def test_file_tools(test_home_dir):
    """Create test instances of file tools."""
    # Create a working directory that's not the home directory
    with tempfile.TemporaryDirectory() as work_dir:
        # Create some test files in the working dir
        Path(work_dir, "workspace_file.txt").write_text("Workspace file content")
        Path(work_dir, "data").mkdir()
        Path(work_dir, "data", "nested_file.txt").write_text("Nested content")

        # Create path resolver and tools with the working directory as root
        resolver = FilePathResolver(root_dir=work_dir)
        read_tool = ReadFileTool(root_dir=work_dir)
        write_tool = WriteFileTool(root_dir=work_dir)

        yield {
            "resolver": resolver,
            "read_tool": read_tool,
            "write_tool": write_tool,
            "home_dir": test_home_dir,
            "work_dir": Path(work_dir),
        }


def test_home_path_expansion(test_file_tools):
    """Test home directory path expansion."""
    resolver = test_file_tools["resolver"]

    # Test with home directory using tilde notation
    home_path = "~/.aki/config.json"
    expanded_path = resolver.resolve_path(home_path, operation=OPERATION_READ)

    # Check that path was expanded correctly
    # Use Path objects for comparison to handle /var vs /private/var symlinks on macOS
    assert expanded_path.name == "config.json"
    assert ".aki" in str(expanded_path)
    # Verify the path exists
    assert expanded_path.exists()


def test_absolute_path_read(test_file_tools):
    """Test handling of absolute paths for read operations."""
    resolver = test_file_tools["resolver"]
    home_dir = test_file_tools["home_dir"]

    # Build absolute path to file
    abs_path = str(home_dir / ".aki" / "test_file.txt")

    # Test with absolute path for reading
    result_path = resolver.resolve_path(abs_path, operation=OPERATION_READ)

    # Verify path is correct and exists
    assert result_path.name == Path(abs_path).name
    assert result_path.exists()


def test_absolute_path_write_allowed(test_file_tools):
    """Test handling of absolute paths for write operations within allowed directories."""
    resolver = test_file_tools["resolver"]
    home_dir = test_file_tools["home_dir"]

    # Build absolute path to whitelisted file
    abs_path = str(home_dir / ".aki" / "new_file.txt")

    # Test with absolute path to whitelisted directory
    result_path = resolver.resolve_path(abs_path, operation=OPERATION_WRITE)

    # Verify path is correct
    assert result_path.name == Path(abs_path).name
    assert ".aki" in str(result_path)


def test_absolute_path_write_denied(test_file_tools):
    """Test handling of absolute paths for write operations outside allowed directories."""
    resolver = test_file_tools["resolver"]
    home_dir = test_file_tools["home_dir"]

    # Build absolute path to non-whitelisted file
    abs_path = str(home_dir / "regular_file.txt")

    # Test with absolute path outside allowed areas
    with pytest.raises(AccessDeniedError):
        resolver.resolve_path(abs_path, operation=OPERATION_WRITE)


def test_relative_path(test_file_tools):
    """Test handling of relative paths."""
    resolver = test_file_tools["resolver"]

    # Test with relative path
    rel_path = "workspace_file.txt"
    result_path = resolver.resolve_path(rel_path, operation=OPERATION_READ)

    # Path should be resolved relative to working directory
    assert result_path.name == "workspace_file.txt"
    assert result_path.exists()


def test_nested_relative_path(test_file_tools):
    """Test handling of nested relative paths."""
    resolver = test_file_tools["resolver"]

    # Test with nested relative path
    nested_path = "data/nested_file.txt"
    result_path = resolver.resolve_path(nested_path, operation=OPERATION_READ)

    # Path should be resolved relative to working directory
    assert result_path.name == "nested_file.txt"
    assert "data" in str(result_path)
    assert result_path.exists()


def test_parent_directory_path_read(test_file_tools):
    """Test handling of paths that navigate outside working directory for read operations."""
    resolver = test_file_tools["resolver"]
    work_dir = test_file_tools["work_dir"]

    # Create a file in the parent directory
    parent_dir = work_dir.parent
    outside_file = parent_dir / "outside_file.txt"
    outside_file.write_text("This is an outside file")

    # Test with path trying to go up the directory tree
    parent_path = "../outside_file.txt"
    # This should not raise an error for read operations
    result_path = resolver.resolve_path(parent_path, operation=OPERATION_READ)

    # Ensure the path name is preserved
    assert result_path.name == "outside_file.txt"
    # Check that path is outside the workspace
    assert not work_dir.samefile(result_path.parent)


def test_parent_directory_path_write(test_file_tools):
    """Test handling of paths that navigate outside working directory for write operations."""
    resolver = test_file_tools["resolver"]

    # Test with path trying to go up the directory tree
    parent_path = "../outside_file.txt"

    # This should raise an AccessDeniedError for write operations
    with pytest.raises(AccessDeniedError):
        resolver.resolve_path(parent_path, operation=OPERATION_WRITE)


def test_read_tool_resolve(test_file_tools):
    """Test path resolution in ReadFileTool."""
    read_tool = test_file_tools["read_tool"]
    home_dir = test_file_tools["home_dir"]

    # Test with absolute path to file
    abs_path = str(home_dir / ".aki" / "config.json")

    # This should return a valid path string (not an error message)
    result_path = read_tool.resolve_path(abs_path)
    assert not result_path.startswith("Error:")

    # Reading outside workspace should be allowed
    outside_path = str(home_dir / "regular_file.txt")
    result_path = read_tool.resolve_path(outside_path)
    assert not result_path.startswith("Error:")


def test_write_tool_resolve(test_file_tools):
    """Test path resolution in WriteFileTool."""
    write_tool = test_file_tools["write_tool"]
    home_dir = test_file_tools["home_dir"]
    work_dir = test_file_tools["work_dir"]

    # Test with workspace path (should succeed)
    workspace_path = "new_file.txt"
    result_path = write_tool.resolve_path(workspace_path)
    assert not result_path.startswith("Error:")

    # Test with whitelisted path (should succeed)
    whitelisted_path = str(home_dir / ".aki" / "new_file.txt")
    result_path = write_tool.resolve_path(whitelisted_path)
    assert not result_path.startswith("Error:")

    # Test with non-whitelisted path (should fail)
    non_whitelisted = str(home_dir / "new_file.txt")
    result_path = write_tool.resolve_path(non_whitelisted)
    assert result_path.startswith("Error: Access denied")
    assert str(work_dir) in result_path  # Should mention allowed directory


def test_nonexistent_file(test_file_tools):
    """Test handling of non-existent files."""
    resolver = test_file_tools["resolver"]

    # Test with non-existent file
    nonexistent = "does_not_exist.txt"

    # This should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        resolver.resolve_path(nonexistent, operation=OPERATION_READ)

    # For non-existent files, write operations should not raise FileNotFoundError
    # (only the parent directory needs to exist)
    result_path = resolver.resolve_path(nonexistent, operation=OPERATION_WRITE)
    assert result_path.name == "does_not_exist.txt"


def test_effective_root(test_file_tools):
    """Test get_effective_root method."""
    resolver = test_file_tools["resolver"]
    work_dir = test_file_tools["work_dir"]

    # Get effective root
    root_path = resolver.get_effective_root()

    # Should be the working directory
    assert str(root_path) == str(work_dir)
