import os
import json
import pytest
import tempfile
from pathlib import Path

from aki.tools.file_management.file_search import FileSearchTool


@pytest.fixture
def test_directory():
    """Create a temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        files = {
            "test1.py": 'import os\nprint("Hello")',
            "test2.py": 'import sys\nprint("World")',
            "test3.txt": "This is a text file",
            ".hidden.txt": "Hidden file content",
            "subdir/nested.py": "def test():\n    pass",
            "node_modules/lib.js": 'console.log("test")',
            "build/output.txt": "Build output",
        }

        # Create .gitignore
        gitignore_content = """
# Python cache
__pycache__/
*.pyc

# Node modules
node_modules/

# Build directory
build/
"""

        for filepath, content in files.items():
            full_path = Path(tmpdir) / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Write .gitignore
        gitignore_path = Path(tmpdir) / ".gitignore"
        gitignore_path.write_text(gitignore_content)

        yield tmpdir


def test_filename_pattern_search(test_directory):
    """Test searching by filename pattern using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)
    result_json = json.loads(tool._run(pattern="*.py", dir_path="."))

    # Check matches
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test1.py" in found_files
    assert "test2.py" in found_files
    assert "subdir/nested.py" in found_files

    # Verify no text files found
    for match in result_json["matches"]:
        assert not match["path"].endswith(".txt")


def test_hidden_files(test_directory):
    """Test hidden files inclusion/exclusion using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Test without including hidden files
    result_json = json.loads(tool._run(pattern="*.txt", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test3.txt" in found_files
    assert ".hidden.txt" not in found_files

    # Test with including hidden files
    result_json = json.loads(
        tool._run(pattern="*.txt", dir_path=".", include_hidden=True)
    )
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test3.txt" in found_files
    assert ".hidden.txt" in found_files


def test_gitignore_respect(test_directory):
    """Test gitignore pattern respect using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Test with gitignore respected (default)
    result_json = json.loads(tool._run(pattern="*.*", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "node_modules/lib.js" not in found_files  # in node_modules/
    assert "build/output.txt" not in found_files  # in build/
    assert "test1.py" in found_files

    # Test with gitignore ignored
    result_json = json.loads(
        tool._run(pattern="*.*", dir_path=".", respect_gitignore=False)
    )
    found_files = {match["path"] for match in result_json["matches"]}
    assert "node_modules/lib.js" in found_files
    assert "build/output.txt" in found_files
    assert "test1.py" in found_files


def test_max_results(test_directory):
    """Test maximum results limit using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Create many files to test max_results
    for i in range(10):
        filepath = Path(test_directory) / f"many_{i}.py"
        filepath.write_text(f"# File {i}")

    # Test with max_results=3
    result_json = json.loads(tool._run(pattern="*.py", dir_path=".", max_results=3))

    # Should have at most 3 matches
    assert len(result_json["matches"]) <= 3
    # But total_matches should be higher or equal to 3
    assert result_json["total_matches"] >= 3


def test_invalid_directory():
    """Test handling of invalid directory using JSON output."""
    tool = FileSearchTool()

    result_json = json.loads(
        tool._run(pattern="*.py", dir_path="/nonexistent/directory")
    )

    # Check for error
    assert result_json["error"] is not None
    assert (
        "not found" in result_json["error"].lower()
        or "no such" in result_json["error"].lower()
    )
    assert len(result_json["matches"]) == 0


def test_pattern_matching(test_directory):
    """Test various pattern matching scenarios using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Test exact match
    result_json = json.loads(tool._run(pattern="test1.py", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test1.py" in found_files
    assert "test2.py" not in found_files

    # Test wildcard patterns
    result_json = json.loads(tool._run(pattern="test?.py", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test1.py" in found_files
    assert "test2.py" in found_files

    # Test character class
    result_json = json.loads(tool._run(pattern="test[12].py", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test1.py" in found_files
    assert "test2.py" in found_files

    # Make sure text files aren't matched
    assert all(not file.endswith(".txt") for file in found_files)


def test_brace_expansion(test_directory):
    """Test brace expansion pattern matching using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Create additional test files
    files = {
        "test.java": "Java content",
        "test.xml": "XML content",
        "test.yaml": "YAML content",
    }
    for filepath, content in files.items():
        full_path = Path(test_directory) / filepath
        full_path.write_text(content)

    # Test brace expansion using wcmatch pipe syntax
    result_json = json.loads(tool._run(pattern="*.java|*.xml", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test.java" in found_files
    assert "test.xml" in found_files
    assert "test.yaml" not in found_files

    # Test multiple patterns
    result_json = json.loads(tool._run(pattern="*.java|*.yaml", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test.java" in found_files
    assert "test.xml" not in found_files
    assert "test.yaml" in found_files


def test_multiple_patterns(test_directory):
    """Test multiple pattern matching using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Test pipe-separated patterns (wcmatch syntax)
    result_json = json.loads(tool._run(pattern="*.py|*.txt", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "test1.py" in found_files
    assert "test2.py" in found_files
    assert "test3.txt" in found_files


def test_recursive_pattern(test_directory):
    """Test recursive pattern matching with ** using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Create nested directory structure
    nested_files = {
        "src/main/main.java": "content",
        "src/test/test.java": "content",
        "src/main/main.xml": "content",
    }
    for filepath, content in nested_files.items():
        full_path = Path(test_directory) / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    # Test recursive matching (default behavior)
    result_json = json.loads(tool._run(pattern="*.java", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "src/main/main.java" in found_files
    assert "src/test/test.java" in found_files
    assert all(not file.endswith(".xml") for file in found_files)

    # Test non-recursive mode
    result_json = json.loads(tool._run(pattern="*.java", dir_path=".", recursive=False))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "src/main/main.java" not in found_files  # Should not find nested files
    assert "src/test/test.java" not in found_files

    # Test explicit recursive pattern (should work the same as default)
    result_json = json.loads(tool._run(pattern="src/**/*.java", dir_path="."))
    found_files = {match["path"] for match in result_json["matches"]}
    assert "src/main/main.java" in found_files
    assert "src/test/test.java" in found_files
    assert all(not file.endswith(".xml") for file in found_files)


def test_complex_patterns(test_directory):
    """Test complex pattern combinations using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Create complex directory structure
    complex_files = {
        "src/main/test.java": "content",
        "src/main/util.py": "content",
        "test/unit/test.java": "content",
        "test/unit/test.py": "content",
    }
    for filepath, content in complex_files.items():
        full_path = Path(test_directory) / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    # Test complex pattern with pipe syntax for wcmatch
    result_json = json.loads(
        tool._run(pattern="src/**/*.java|test/**/*.java", dir_path=".")
    )
    found_files = {match["path"] for match in result_json["matches"]}
    assert "src/main/test.java" in found_files
    assert "test/unit/test.java" in found_files
    assert all(not file.endswith(".py") for file in found_files)


def test_pattern_error_handling(test_directory):
    """Test error handling for invalid patterns using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)

    # Test invalid pattern with unmatched bracket
    result_json = json.loads(tool._run(pattern="*.[abc", dir_path="."))

    # Check that no matches were found
    assert len(result_json["matches"]) == 0
    assert result_json["total_matches"] == 0


def test_path_resolution(test_directory):
    """Test path resolution in search results using JSON output."""
    tool = FileSearchTool(root_dir=test_directory)
    result_json = json.loads(tool._run(pattern="*.py", dir_path="."))

    # Check that paths are properly resolved
    assert result_json["original_path"] == "."
    assert result_json["resolved_path"] is not None

    # The resolved path should include the test directory
    resolved_path = result_json["resolved_path"]
    assert (
        test_directory in resolved_path
        or os.path.realpath(test_directory) in resolved_path
    )
