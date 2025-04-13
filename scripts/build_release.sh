#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Script to run lint, coverage tests, and build in sequence
echo "🚀 Starting Aki build process..."

# Define colors for output
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# Make sure we're in the project root directory
cd "$(dirname "$0")/.." || exit 1

echo -e "${YELLOW}Current directory: $(pwd)${NC}"

# 1. Run linting with Black and Ruff
echo -e "\n${YELLOW}Step 1/4: Running code formatter (black)...${NC}"
uv run black src tests
uv run ruff check --fix src tests --ignore E402
echo -e "${GREEN}✓ Formatting complete${NC}"

# 2. Run pytest with coverage
echo -e "\n${YELLOW}Step 2/4: Running test suite with coverage...${NC}"
PYTHONPATH=src uv run coverage run -m pytest --asyncio-mode=strict
echo -e "${GREEN}✓ Tests complete${NC}"

# 3. Generate coverage report
echo -e "\n${YELLOW}Step 3/4: Generating coverage report...${NC}"
PYTHONPATH=src uv run coverage report -m
PYTHONPATH=src uv run coverage html
echo -e "${GREEN}✓ Coverage report generated in htmlcov/ directory${NC}"

# 4. Build the package
echo -e "\n${YELLOW}Step 4/4: Building Python package...${NC}"
uv run hatch build
echo -e "${GREEN}✓ Build complete${NC}"

echo -e "\n${GREEN}🎉 All tasks completed successfully!${NC}"
echo "Distribution files are available in dist/"
echo "Coverage report is available in htmlcov/index.html"

# Optional: Open coverage report in browser
if [[ "$1" == "--open-report" || "$1" == "-o" ]]; then
  echo "Opening coverage report in browser..."
  # Try different commands based on OS
  if [[ "$(uname)" == "Darwin" ]]; then
    open htmlcov/index.html
  elif [[ "$(uname)" == "Linux" ]]; then
    xdg-open htmlcov/index.html 2>/dev/null || sensible-browser htmlcov/index.html 2>/dev/null || echo "Please open htmlcov/index.html manually"
  elif [[ "$(uname)" == "MINGW"* || "$(uname)" == "MSYS"* || "$(uname)" == "CYGWIN"* ]]; then
    start htmlcov/index.html
  fi
fi