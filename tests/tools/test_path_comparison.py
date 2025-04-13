import os
import pytest
import tempfile
from pathlib import Path

from aki.tools.file_management.read import ReadFileTool
from aki.tools.file_management.file_paths import FilePathResolver


# Helper function for path comparison
def is_relative_to(path: Path, root: Path) -> bool:
    """Check if path is a subpath of root."""
    try:
        # Try to handle potential symlink differences between /var and /private/var on macOS
        path_str = str(path.resolve())
        root_str = str(root.resolve())
        if path_str.startswith(root_str + "/") or path_str == root_str:
            return True

        # Fall back to standard method if the string comparison fails
        path.relative_to(root)
        return True
    except (ValueError, AttributeError):
        return False


@pytest.fixture
def test_paths():
    """Create test paths for comparison testing."""
    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        root_dir = Path(tmpdir)

        # Create directories and files for testing
        (root_dir / "subdir").mkdir()
        (root_dir / "subdir" / "file.txt").write_text("test content")
        (root_dir / "another").mkdir()
        (root_dir / "another" / "nested").mkdir()
        (root_dir / "another" / "nested" / "deep_file.txt").write_text("nested content")

        # Create paths with different formats but pointing to the same location
        same_paths = [
            root_dir / "subdir",
            root_dir / "." / "subdir",
            (root_dir / "another" / "..").resolve() / "subdir",
        ]

        # Create paths for testing is_relative_to
        inside_paths = [
            root_dir / "subdir" / "file.txt",
            root_dir / "another" / "nested" / "deep_file.txt",
        ]

        outside_paths = [
            (
                Path("/tmp") / "outside.txt"
                if os.path.exists("/tmp")
                else Path.home() / "outside.txt"
            ),
            Path.home() / "outside_dir" / "file.txt",
        ]

        yield {
            "root_dir": root_dir,
            "same_paths": same_paths,
            "inside_paths": inside_paths,
            "outside_paths": outside_paths,
        }


def test_path_equality_same_paths(test_paths):
    """Test equality of different path formats pointing to the same location."""
    # All paths in same_paths should be equal when resolved
    paths = test_paths["same_paths"]

    # Resolve all paths
    resolved_paths = [p.resolve() for p in paths]

    # Check that all resolved paths are equal
    first_path = resolved_paths[0]
    for path in resolved_paths[1:]:
        assert path == first_path


def test_is_relative_to_inside(test_paths):
    """Test is_relative_to function with paths inside root."""
    root_dir = test_paths["root_dir"]
    inside_paths = test_paths["inside_paths"]

    # All inside paths should be relative to root
    for path in inside_paths:
        assert is_relative_to(path, root_dir) is True


def test_is_relative_to_outside(test_paths):
    """Test is_relative_to function with paths outside root."""
    root_dir = test_paths["root_dir"]
    outside_paths = test_paths["outside_paths"]

    # All outside paths should not be relative to root
    for path in outside_paths:
        if path.exists():  # Only check paths that exist
            assert is_relative_to(path, root_dir) is False


def test_is_relative_to_same_paths(test_paths):
    """Test is_relative_to function with paths that resolve to the same location."""
    root_dir = test_paths["root_dir"]
    same_paths = test_paths["same_paths"]

    # All paths should be relative to each other as they point to the same location
    for path in same_paths:
        assert is_relative_to(path, root_dir) is True


@pytest.fixture
def symlink_fixture():
    """Create symlinks for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_dir = Path(tmpdir)

        # Create a file and subdirectory
        test_file = root_dir / "test_file.txt"
        test_file.write_text("Test content")

        subdir = root_dir / "subdir"
        subdir.mkdir()

        # Create symlinks
        try:
            file_link = root_dir / "file_link.txt"
            os.symlink(test_file, file_link)

            dir_link = root_dir / "dir_link"
            os.symlink(subdir, dir_link)

            # Create a path that goes through a symlink
            through_link = dir_link / "nested" / "file.txt"

            yield {
                "root_dir": root_dir,
                "test_file": test_file,
                "file_link": file_link,
                "subdir": subdir,
                "dir_link": dir_link,
                "through_link": through_link,
            }
        except (OSError, PermissionError):
            pytest.skip("Symlink creation failed - permissions or platform limitations")


def test_symlink_resolution(symlink_fixture):
    """Test path resolution through symlinks."""
    try:
        file_link = symlink_fixture["file_link"]
        test_file = symlink_fixture["test_file"]

        # Verify the symlink points to the correct file
        assert file_link.resolve() == test_file.resolve()

        # Check that content is accessible through the symlink
        assert file_link.read_text() == "Test content"
    except (OSError, PermissionError):
        pytest.skip("Symlink tests not supported on this platform")


def test_path_resolver_init():
    """Test initializing FilePathResolver."""
    # Test with no arguments
    resolver = FilePathResolver()
    assert resolver.root_dir is None

    # Test with root_dir specified
    resolver = FilePathResolver(root_dir="/tmp")
    assert resolver.root_dir == "/tmp"


@pytest.fixture
def absolute_path_fixture():
    """Create a fixture for testing absolute paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a project-like directory structure
        project_dir = Path(tmpdir) / "Aki" / "src" / "Aki"
        os.makedirs(project_dir)

        # Create nested directories similar to the actual project
        nested_dir = project_dir / "src" / "aki" / "profiles" / "prompts"
        os.makedirs(nested_dir)

        # Create a test file
        test_file = nested_dir / "aki.txt"
        test_file.write_text("Test content")

        # Create an absolute path to the file
        absolute_path = test_file.resolve()

        # Create a read tool with the project directory as root
        read_tool = ReadFileTool(root_dir=str(project_dir))

        yield {
            "project_dir": project_dir,
            "test_file": test_file,
            "absolute_path": str(absolute_path),
            "read_tool": read_tool,
        }


def test_absolute_path_validation(absolute_path_fixture):
    """Test validating absolute paths with ReadFileTool."""
    fixture = absolute_path_fixture
    read_tool = fixture["read_tool"]
    project_dir = fixture["project_dir"]

    # Test with path inside project directory
    valid_path = str(project_dir / "src" / "file.txt")
    assert is_relative_to(Path(valid_path), project_dir) is True

    # Create the file so it exists
    Path(valid_path).parent.mkdir(exist_ok=True)
    Path(valid_path).write_text("Test content")

    # Use resolve_path directly
    resolved_path = read_tool.resolve_path(valid_path)
    assert not resolved_path.startswith("Error:")

    # Test with absolute path to test file
    abs_path = fixture["absolute_path"]
    Path(abs_path).parent.mkdir(exist_ok=True, parents=True)
    Path(abs_path).write_text("Test content")

    resolved_path = read_tool.resolve_path(abs_path)
    assert not resolved_path.startswith("Error:")
