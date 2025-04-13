import os
import pytest
import tempfile
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from aki.tools.file_management.grep_tool import GrepTool


@pytest.fixture
def test_directory():
    """Create a temporary directory with test files for grepping."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files with different modification times
        files = {
            "file1.py": '# TODO: This is a Python task\nprint("Hello World")\n# Another TODO item',
            "file2.js": 'function hello() {\n  // TODO: Implement this\n  console.log("Not implemented");\n}',
            "file3.txt": "This is a text file without TODOs",
            "logs/error.log": "ERROR: Something went wrong\nWARNING: Just a warning\nERROR: Another error",
            "src/module.py": "class TestClass:\n    def test_function(self):\n        pass\n    # TODO: Add more functions",
            ".hidden/config.txt": "TODO: Update configuration",
        }

        # Create the files with different timestamps
        now = datetime.now()
        for i, (filepath, content) in enumerate(files.items()):
            full_path = Path(tmpdir) / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

            # Set modification time to different times (older as we go down the list)
            mtime = now - timedelta(hours=i)
            os.utime(full_path, (mtime.timestamp(), mtime.timestamp()))

        yield tmpdir


def is_ripgrep_available():
    """Check if ripgrep is available on the system."""
    try:
        subprocess.run(["rg", "--version"], capture_output=True, text=True, check=False)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


# Only run tests if ripgrep is available
@pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not available")
def test_basic_search(test_directory):
    """Test basic grep functionality."""
    tool = GrepTool()

    # Search for TODO comments
    result = tool._run(pattern="TODO", path=test_directory)

    # For raw output, we just check that it contains expected content
    assert result is not None
    assert "TODO" in result
    assert "Python" in result or "file1.py" in result


@pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not available")
def test_file_filtering(test_directory):
    """Test filtering by glob pattern."""
    tool = GrepTool()

    # Search only in Python files
    result_py = tool._run(pattern="TODO", path=test_directory, glob="*.py")

    # Search only in JS files
    result_js = tool._run(pattern="TODO", path=test_directory, glob="*.js")

    # Check if results contain appropriate file extensions
    assert ".py" in result_py
    assert ".js" in result_js
    assert ".js" not in result_py
    assert ".py" not in result_js


@pytest.mark.skipif(not is_ripgrep_available(), reason="ripgrep not available")
def test_path_resolution(test_directory):
    """Test proper path resolution."""
    tool = GrepTool()

    # Test with relative path (should work)
    relative_result = tool._run(pattern="TODO", path=test_directory)
    assert "TODO" in relative_result

    # Test with nonexistent path (should return error message)
    nonexistent_path = os.path.join(test_directory, "nonexistent_dir")
    error_result = tool._run(pattern="TODO", path=nonexistent_path)
    assert "Error" in error_result or "error" in error_result.lower()
