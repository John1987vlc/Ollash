#!/bin/bash
# Run comprehensive test suite for Ollash Cowork improvements

# Ensure we're running from the project root
cd "$(dirname "$0")/.."

echo "=========================================="
echo "Ollash Test Suite - Cowork Improvements"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo -e "${RED}Error: Python is not installed${NC}"
    exit 1
fi

# Check if pytest is installed
if ! python -m pytest --version &> /dev/null; then
    echo -e "${YELLOW}Installing pytest and dependencies...${NC}"
    pip install -q pytest pytest-mock pytest-cov
fi

echo -e "${YELLOW}Running unit tests...${NC}"
echo ""

# Run tests with coverage
python -m pytest tests/unit/ \
    -v \
    --tb=short \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    -m "unit"

TEST_RESULT=$?

echo ""
echo "=========================================="

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Coverage report generated in htmlcov/index.html"
else
    echo -e "${RED}✗ Some tests failed!${NC}"
    exit 1
fi

echo "=========================================="
