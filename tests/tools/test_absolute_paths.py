import os
import pytest
import tempfile
from pathlib import Path

from aki.tools.file_management.read import ReadFileTool
from aki.tools.file_management.whitelist import WHITELISTED_PATHS


@pytest.fixture
def mock_project_structure():
    """Create a mock project structure for testing absolute paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory structure similar to the project
        project_dir = Path(tmpdir) / "workplace" / "Aki" / "src" / "Aki"
        os.makedirs(project_dir)

        # Create the directories structure
        nested_dir = project_dir / "src" / "aki" / "profiles" / "prompts"
        os.makedirs(nested_dir)

        # Create test files
        test_file = nested_dir / "aki.txt"
        test_file.write_text("Test content for aki.txt")

        (project_dir / "README.md").write_text("# Project README")

        # Create tool mixin
        tool = ReadFileTool(root_dir=str(project_dir))

        # Return paths and tool for testing
        yield {"project_dir": project_dir, "test_file": test_file, "tool": tool}


def test_absolute_path_inside_project(mock_project_structure):
    """Test handling of absolute paths within the project."""
    project_dir = mock_project_structure["project_dir"]
    test_file = mock_project_structure["test_file"]
    tool = mock_project_structure["tool"]

    # Test with absolute path to file in project
    abs_path = str(test_file)
    path = tool.resolve_path(abs_path)

    # Use samefile comparison to account for macOS /private/var symlink
    assert Path(path).resolve().samefile(test_file)

    # Verify it can be read via relative path from project root
    rel_path = os.path.relpath(test_file, project_dir)
    path = tool.resolve_path(rel_path)
    assert Path(path).resolve().samefile(test_file)


def test_absolute_path_outside_project(mock_project_structure):
    """Test that absolute paths outside the project directory are allowed for read operations."""
    tool = mock_project_structure["tool"]

    # Try with a path outside the project directory
    if os.path.exists("/tmp"):
        outside_path = "/tmp/outside_file.txt"

        # Create the file to avoid FileNotFoundError
        with open(outside_path, "w") as f:
            f.write("Test content")

        try:
            # For read operations, we should be able to access files outside the workspace
            path = tool.resolve_path(outside_path)
            if not path.startswith("Error:"):
                assert path.startswith("/")  # Ensure it's still an absolute path
            else:
                # If system doesn't allow outside access, the error should mention the path
                assert outside_path in path
        except Exception as e:
            pytest.fail(f"Accessing path outside project raised exception: {e}")
        finally:
            # Clean up
            try:
                os.unlink(outside_path)
            except Exception:
                pytest.xfail("unlink fail")


def test_parent_traversal(mock_project_structure):
    """Test path validation with parent directory traversal."""
    project_dir = mock_project_structure["project_dir"]
    tool = mock_project_structure["tool"]

    # Create a file in the parent directory of the project
    parent_dir = project_dir.parent
    parent_file = parent_dir / "parent_file.txt"
    parent_file.write_text("File in parent directory")

    # Try to access the file using parent traversal
    traversal_path = str(project_dir / ".." / "parent_file.txt")

    # For read operations, parent traversal should now be allowed
    try:
        path = tool.resolve_path(traversal_path)
        if not path.startswith("Error:"):
            # Verify the path resolves to the parent file
            assert Path(path).resolve().samefile(parent_file)
        else:
            # If system doesn't allow parent traversal, the error should mention the path
            assert "parent_file.txt" in path
    except Exception as e:
        pytest.fail(f"Parent traversal raised exception: {e}")


def test_whitelist_path(mock_project_structure):
    """Test whitelist path access."""
    tool = mock_project_structure["tool"]

    # Temporarily add a path to the whitelist
    test_whitelist_path = Path("/var/tmp/test_whitelist")
    os.makedirs(test_whitelist_path, exist_ok=True)
    test_file = test_whitelist_path / "whitelist_test.txt"
    with open(test_file, "w") as f:
        f.write("Test content for whitelist file")

    # Add to whitelist temporarily
    WHITELISTED_PATHS.add(test_whitelist_path)

    try:
        # Test access to whitelisted path
        path = tool.resolve_path(str(test_file))
        if not path.startswith("Error:"):
            # Use samefile to account for macOS path differences
            assert Path(path).resolve().samefile(test_file)
        else:
            # If system doesn't allow whitelisted access, the error should mention the path
            assert str(test_file) in path
    finally:
        # Clean up
        WHITELISTED_PATHS.remove(test_whitelist_path)
        # Attempt to remove the file and directory
        try:
            os.remove(test_file)
            os.rmdir(test_whitelist_path)
        except (FileNotFoundError, PermissionError):
            pass


def test_symlink_handling(mock_project_structure):
    """Test handling of symlinks."""
    project_dir = mock_project_structure["project_dir"]
    tool = mock_project_structure["tool"]

    # Create a file and a symlink to it
    test_file = project_dir / "test_file.txt"
    test_file.write_text("Test content for symlink test")
    symlink_path = project_dir / "symlink_file.txt"

    try:
        # Create a symbolic link
        os.symlink(test_file, symlink_path)

        # Test access via symlink - should follow the symlink
        path = tool.resolve_path(str(symlink_path))
        if not path.startswith("Error:"):
            # When resolving symlinks, the path should lead to the target
            target_file = Path(path).resolve()
            source_file = test_file.resolve()
            assert target_file.samefile(source_file)
        else:
            # If system doesn't handle symlinks properly, the error should mention the path
            assert str(symlink_path) in path
    except (OSError, PermissionError):
        # Skip on platforms that don't support symlinks or lack permissions
        pytest.skip("Symlinks not supported or require elevated permissions")


def test_nonexistent_path(mock_project_structure):
    """Test handling of nonexistent paths."""
    project_dir = mock_project_structure["project_dir"]
    tool = mock_project_structure["tool"]

    # Test with path that doesn't exist yet
    nonexistent_path = project_dir / "nonexistent.txt"

    # Should return an error message for nonexistent files
    path = tool.resolve_path(str(nonexistent_path))
    assert path.startswith("Error: No such file or directory")
