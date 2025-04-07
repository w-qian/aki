# Aki

Aki is a highly customizable AI assistant that adapts to your unique workflow. 

## Features
More features coming soon!

### Toolsets
- **Web Search Tool**: Easily integrate web search capabilities using DuckDuckGo or Google Serper API

## Getting started

Aki can be installed using various Python package managers. We recommend using uv for its speed and reliability.

### Install uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
or follow [official instructions](https://docs.astral.sh/uv/getting-started/installation)

### Install pnpm
This is required to build chainlit from source
```bash
curl -fsSL https://get.pnpm.io/install.sh | sh -
```
or follow [official instructions](https://pnpm.io/installation)

### Using uv

```bash
# Install from the project directory
uv tool install --python 3.12 git+https://github.com/Aki-community/aki.git@main
```

### Run aki
```bash
aki
```

## Configuration

### Google Serper API

To use Google Serper API (offers better search results), set the SERPER_API_KEY environment variable:

```bash
export SERPER_API_KEY="your-api-key"
```

If the API key is not available, the tool automatically falls back to using DuckDuckGo search.

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/Aki-community/aki.git
cd aki

# Create a virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Sync dependency
uv sync

# Run aki
uv run aki
```

Install additional dependences for developers (test/lint)
```bash
uv sync --extra dev
```

Add new dependencies
```bash
uv add new-dependency-name
```


### Build Script

Aki provides a comprehensive build script that runs formatting, testing, and building in a single command:

```bash
# Run the complete build process (format, test, coverage, build)
hatch run release
```

This command:
1. Runs code formatting with black
2. Executes all tests with coverage tracking
3. Generates coverage reports (terminal and HTML)
4. Builds the package using hatch

### Running Tests

Aki uses pytest for testing. Run the tests with:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_app.py

# Run tests with coverage report
coverage run -m pytest
```

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the tests to ensure they pass (`pytest`)
5. Commit your changes (`git commit -m 'Add some amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Code Style

We follow PEP 8 guidelines for Python code. You can use tools like flake8 and black to ensure your code meets these standards:

```bash
# Install code quality tools
uv pip install flake8 black

# Check code style
flake8 src tests

# Format code
black src tests
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.