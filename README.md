# Aki

Aki is a highly customizable AI assistant that adapts to your unique workflow. 

## Features

Aki provides a rich set of features designed to enhance AI assistant capabilities:

### AI Assistant Profiles
- **Aki**: General-purpose AI assistant for SDEs - handles all tasks with full access to tools
- **Akira**: Research-focused assistant specialized in information retrieval and analysis
- **Akisa**: Software engineering assistant focused on coding tasks and development workflows

### LLM Integration
- **Bedrock**: Seamless integration with Bedrock models
- **Ollama**: Support for running local models via Ollama
- **Customizable providers**: Extensible architecture for adding new LLM providers

### Toolsets
- **Web Search Tool**: Easily integrate web search capabilities using DuckDuckGo or Google Serper API
- **Code Analyzer**: Parse and understand repository structure with language-specific analysis
- **Process Manager**: Control long-running processes and services with monitoring capabilities
- **Task Management**: Create and track multi-step tasks with status tracking
- **File Operations**: Comprehensive file management with security constraints
- **Python Execution**: Execute Python code snippets directly in conversations
- **Shell Commands**: Run system commands from within the assistant interface
- **Batch Tool**: Combine multiple tool operations efficiently
- **HTML Rendering**: Display rich content and interactive elements

### Database System
- **SQLite**: Default lightweight database for storing conversations and state
- **PostgreSQL**: Optional robust database for production environments

### Architecture
- **LangGraph**: Built on LangGraph for powerful agent workflows
- **MCP Integration**: Model Context Protocol support for external system connections
- **Chainlit UI**: Modern, responsive chat interface

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

### LLM Configuration

#### Bedrock

To use Amazon Bedrock models, you need to configure AWS credentials. Aki supports two methods:

##### Option 1: Using a `.aki/.env` file

Edit your existing `~/.aki/.env` file and ensure it contains your AWS credentials:
```
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-west-2
```

This method keeps your AWS credentials isolated to the Aki application.

##### Option 2: Using an AWS profile

1. If you haven't already set up the AWS CLI, install it following the [official instructions](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

2. Configure a profile named `aki` with your credentials:
   ```bash
   aws configure --profile aki
   ```

3. Enter your AWS Access Key ID, Secret Access Key, and preferred region when prompted.

This creates entries in your `~/.aws/credentials` and `~/.aws/config` files.

For both options, ensure your AWS credentials have permissions to access the Bedrock models.

#### Ollama

To use Ollama, ensure the Ollama service is running locally. Aki will automatically detect supported models.

### Google Serper API

To use Google Serper API (offers better search results), set the SERPER_API_KEY environment variable:

```bash
export SERPER_API_KEY="your-api-key"
```

If the API key is not available, the tool automatically falls back to using DuckDuckGo search.

## Development

### Project Structure

Aki is organized into several key modules:

```
aki/
├── app.py                # Main application entry point
├── config/               # Configuration management
├── chat/                 # Chat system components
│   ├── base/             # Base profile classes
│   ├── graph/            # LangGraph agent definitions
│   └── implementations/  # Specific agent implementations
├── llm/                  # LLM provider integration
│   └── providers/        # LLM provider implementations
├── persistence/          # Database and state management
├── profiles/             # AI assistant profile definitions
│   └── prompts/          # System prompts for profiles
├── public/               # UI assets and components
└── tools/                # Tool implementations
    ├── code_analyzer/    # Code analysis tools
    ├── file_management/  # File operation tools
    └── mcp/              # MCP integration
```

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

### Creating Custom Profiles

You can create custom AI assistant profiles by adding JSON configuration files to the `profiles` directory:

```json
{
  "name": "Your Assistant Name",
  "description": "Description of your assistant",
  "system_prompt_file": "prompts/your_prompt.txt",
  "tools": [
    "file_management_readonly",
    "web_search",
    "code_analyzer",
    "tasklist"
  ],
  "default_model": "(bedrock)anthropic.claude-3-sonnet-20240229-v1:0",
  "reasoning_config": {
    "default_enabled": true,
    "budget_tokens": 2048
  }
}
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