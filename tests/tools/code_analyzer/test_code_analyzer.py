import os
import shutil
import tempfile
from typing import Dict

import pytest

# Import necessary modules
from aki.tools.code_analyzer.code_analyzer import (
    CodeAnalyzerTool,
    create_code_analyzer_tool,
)

# Import sample test data
from .python_sample_data import PYTHON_SAMPLE
from .java_sample_data import JAVA_SAMPLE
from .typescript_sample_data import TYPESCRIPT_SAMPLE


# Test fixtures and helpers
@pytest.fixture
def analyzer_tool() -> CodeAnalyzerTool:
    """Return an instance of the CodeAnalyzerTool."""
    return create_code_analyzer_tool()


@pytest.fixture
def temp_dir() -> str:
    """Create a temporary directory for test files."""
    tmp_dir = tempfile.mkdtemp()
    yield tmp_dir
    # Cleanup after tests
    shutil.rmtree(tmp_dir)


def create_file(directory: str, filename: str, content: str) -> str:
    """Create a file with specified content in the given directory."""
    file_path = os.path.join(directory, filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path


def create_test_repository(base_dir: str, file_contents: Dict[str, str]) -> None:
    """Create a test repository with multiple files.

    Args:
        base_dir: Base directory where files should be created
        file_contents: Dictionary mapping relative file paths to their content
    """
    for rel_path, content in file_contents.items():
        create_file(base_dir, rel_path, content)


# Mixed language repository with Python, Java, and TypeScript
MIXED_REPO = {
    **{f"python/{k}": v for k, v in PYTHON_SAMPLE.items()},
    **{f"java/{k}": v for k, v in JAVA_SAMPLE.items()},
    **{f"typescript/{k}": v for k, v in TYPESCRIPT_SAMPLE.items()},
    "README.md": "# Test Repository\nThis repository contains test files for the code analyzer.",
}


# Tests for Python code analysis
@pytest.mark.asyncio
async def test_python_analysis(temp_dir, analyzer_tool):
    """Test analysis of Python code."""
    # Create Python test files
    create_test_repository(temp_dir, PYTHON_SAMPLE)

    # Run analyzer with both tree and content
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Basic assertions for directory structure
    assert "Directory structure:" in result
    assert "sample_module.py" in result
    assert "package/" in result

    # Python-specific assertions based on actual output format
    assert "@decorator" in result
    assert "class SampleClass" in result
    assert "def __init__" in result
    assert "@staticmethod" in result
    assert "def static_method" in result
    assert "@property" in result
    assert "def prop" in result
    assert "def sample_function" in result

    # NOTE: The tool doesn't capture docstrings in its output


@pytest.mark.asyncio
async def test_python_tree_only(temp_dir, analyzer_tool):
    """Test Python analysis with tree structure only."""
    create_test_repository(temp_dir, PYTHON_SAMPLE)

    # Run analyzer with tree only
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": False}
    )

    # Check tree structure
    assert "sample_module.py" in result
    assert "package/" in result
    assert "module.py" in result

    # These should NOT be in the result because include_content=False
    assert "class SampleClass" not in result
    assert "def sample_function" not in result


@pytest.mark.asyncio
async def test_python_content_only(temp_dir, analyzer_tool):
    """Test Python analysis with content only."""
    create_test_repository(temp_dir, PYTHON_SAMPLE)

    # Run analyzer with content only
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": False, "include_content": True}
    )

    # These SHOULD be in the result because include_content=True
    assert "class SampleClass" in result
    assert "def sample_function" in result
    assert "@decorator" in result

    # Tree structure should not be in result
    assert "├──" not in result


# Tests for Java code analysis
@pytest.mark.asyncio
async def test_java_analysis(temp_dir, analyzer_tool):
    """Test analysis of Java code."""
    # Create Java test files
    create_test_repository(temp_dir, JAVA_SAMPLE)

    # Run analyzer with both tree and content
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Basic assertions
    assert "Main.java" in result
    assert "interfaces/" in result
    assert "implementations/" in result

    # Java-specific assertions based on actual output
    assert "public class Main" in result
    assert "public String getName()" in result
    assert "public int getAge()" in result
    assert "public static void main" in result
    assert "System.out.println" in result


@pytest.mark.asyncio
async def test_java_interface_implementation(temp_dir, analyzer_tool):
    """Test that Java interface implementations are correctly analyzed."""
    # Create Java test files, focusing on interface implementation
    java_files = {
        "interfaces/Runnable.java": JAVA_SAMPLE["interfaces/Runnable.java"],
        "implementations/Task.java": JAVA_SAMPLE["implementations/Task.java"],
    }
    create_test_repository(temp_dir, java_files)

    # Run analyzer
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Check interface and implementation based on actual output
    assert "public interface Runnable" in result
    assert "void run()" in result  # Interface method
    assert "public class Task implements Runnable" in result
    assert "public void run()" in result  # Implementation method
    assert "System.out.println" in result


# Tests for TypeScript code analysis
@pytest.mark.asyncio
async def test_typescript_analysis(temp_dir, analyzer_tool):
    """Test analysis of TypeScript code."""
    # Create TypeScript test files
    create_test_repository(temp_dir, TYPESCRIPT_SAMPLE)

    # Run analyzer with both tree and content
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Basic assertions
    assert "app.ts" in result
    assert "models/" in result

    # TypeScript-specific assertions based on actual output
    assert "interface AppConfig" in result
    assert "port: number" in result
    assert "debug: boolean" in result


@pytest.mark.asyncio
async def test_typescript_interfaces(temp_dir, analyzer_tool):
    """Test that TypeScript interfaces are correctly analyzed."""
    # Create just the user model file
    create_test_repository(temp_dir, {"user.ts": TYPESCRIPT_SAMPLE["models/user.ts"]})

    # Run analyzer
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Check interface definition based on actual output
    assert "export interface User" in result
    assert "id: number" in result
    assert "name: string" in result
    assert "email: string" in result


# Tests for mixed language repositories
@pytest.mark.asyncio
async def test_mixed_repository(temp_dir, analyzer_tool):
    """Test analysis of a mixed language repository."""
    # Create a mixed repository with Python, Java, and TypeScript files
    create_test_repository(temp_dir, MIXED_REPO)

    # Run analyzer with both tree and content
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Basic structure assertions
    assert "python/" in result
    assert "java/" in result
    assert "typescript/" in result
    assert "README.md" in result

    # Basic content detection - verify just one element from each language
    # Python code detection
    assert "class SampleClass" in result

    # Java code detection
    assert "public class Main" in result

    # TypeScript code detection
    assert "interface AppConfig" in result


@pytest.mark.asyncio
async def test_nested_directory_structure(temp_dir, analyzer_tool):
    """Test that the analyzer correctly handles nested directory structures."""
    # Create a more complex directory structure
    nested_repo = {
        "src/main/python/app.py": "def main():\n    print('Hello World')",
        "src/main/java/App.java": "public class App {\n    public static void main(String[] args) {}\n}",
        "src/test/python/test_app.py": "def test_main():\n    assert True",
        "src/test/java/AppTest.java": "public class AppTest {\n    @Test\n    public void testApp() {}\n}",
        "docs/README.md": "# Documentation",
        "config/settings.json": '{\n    "debug": true\n}',
    }

    create_test_repository(temp_dir, nested_repo)

    # Run analyzer
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Check directory structure
    assert "src/" in result
    assert "main/" in result
    assert "python/" in result
    assert "java/" in result
    assert "test/" in result
    assert "docs/" in result
    assert "config/" in result

    # Simplified content checks based on actual output
    assert "def main" in result
    assert "public class App" in result


@pytest.mark.asyncio
async def test_excluded_files_and_directories(temp_dir, analyzer_tool):
    """Test that the analyzer correctly excludes files based on patterns."""
    # Create files that should be excluded by default patterns
    excluded_files = {
        ".git/config": "[core]\n\trepositoryformatversion = 0\n",
        "node_modules/package/index.js": "module.exports = {}",
        "__pycache__/module.cpython-310.pyc": "# Binary content would go here",
        "build/output.txt": "Build output",
        ".DS_Store": "# Binary content",
    }

    # Create normal files that shouldn't be excluded
    normal_files = {"src/app.py": "def main():\n    pass", "README.md": "# Project"}

    # Combine all files
    all_files = {**excluded_files, **normal_files}
    create_test_repository(temp_dir, all_files)

    # Run analyzer
    result = await analyzer_tool.ainvoke(
        {"dir_path": temp_dir, "include_tree": True, "include_content": True}
    )

    # Check that normal files are included
    assert "src/" in result
    assert "README.md" in result

    # Check that excluded files are not included
    assert ".git/config" not in result
    assert "node_modules/" not in result
    assert "__pycache__/" not in result
    assert "build/output.txt" not in result
    assert ".DS_Store" not in result
