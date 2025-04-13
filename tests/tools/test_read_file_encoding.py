"""Tests for read_file tool with encoding detection."""

import pytest
import tempfile
import json
from pathlib import Path

from aki.tools.file_management.read import ReadFileTool


@pytest.fixture
def encoding_test_files():
    """Create test files with different encodings for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory structure for testing
        test_dir = Path(tmpdir) / "test_files"
        test_dir.mkdir()

        # Create UTF-8 test file
        utf8_file = test_dir / "utf8_file.txt"
        utf8_content = (
            "This is a UTF-8 encoded file with some special characters: áéíóú ñ €"
        )
        utf8_file.write_text(utf8_content, encoding="utf-8")

        # Create ISO-8859-1 (Latin-1) test file
        latin1_file = test_dir / "latin1_file.txt"
        latin1_content = (
            "This is a Latin-1 encoded file with some special characters: áéíóú ñ"
        )
        with open(latin1_file, "w", encoding="iso-8859-1") as f:
            f.write(latin1_content)

        # Create a binary file which is not text-decodable
        binary_file = test_dir / "binary_file.bin"
        with open(binary_file, "wb") as f:
            f.write(bytes(range(256)))

        # Create read tool instance
        read_tool = ReadFileTool(root_dir=str(test_dir))

        yield {
            "test_dir": test_dir,
            "utf8_file": utf8_file,
            "latin1_file": latin1_file,
            "binary_file": binary_file,
            "read_tool": read_tool,
        }


def test_read_file_utf8_encoding(encoding_test_files):
    """Test read_file correctly detects and handles UTF-8 encoding."""
    read_tool = encoding_test_files["read_tool"]
    utf8_file = encoding_test_files["utf8_file"]

    # Get result as JSON for detailed inspection
    result = read_tool._run(str(utf8_file))
    result_dict = json.loads(result)

    # Check encoding
    assert result_dict["metadata"]["encoding"].lower() in [
        "utf-8",
        "utf8",
        "ascii",
    ], f"Expected UTF-8 encoding, got {result_dict['metadata']['encoding']}"

    # Check content
    assert "special characters: áéíóú" in result_dict["content"]
    assert "€" in result_dict["content"]


def test_read_file_latin1_encoding(encoding_test_files):
    """Test read_file correctly detects and handles Latin-1 encoding."""
    read_tool = encoding_test_files["read_tool"]
    latin1_file = encoding_test_files["latin1_file"]

    # Get result as JSON for detailed inspection
    result = read_tool._run(str(latin1_file))
    result_dict = json.loads(result)

    # Check that we have encoding information
    assert "encoding" in result_dict["metadata"]

    # We only need to check that some content was successfully read
    # The exact representation might vary based on the detected encoding
    assert "Latin-1 encoded file" in result_dict["content"]


def test_read_file_binary(encoding_test_files):
    """Test read_file handles binary files gracefully."""
    read_tool = encoding_test_files["read_tool"]
    binary_file = encoding_test_files["binary_file"]

    # Get result as JSON for detailed inspection
    result = read_tool._run(str(binary_file))
    result_dict = json.loads(result)

    # Check that we get an error for binary files
    assert result_dict["error"] is not None
    assert (
        "binary" in result_dict["metadata"]["encoding"].lower()
        or "Cannot read binary file" in result_dict["error"]
    )
