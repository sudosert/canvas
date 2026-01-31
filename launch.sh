#!/bin/bash
# SD Image Viewer Launcher Script
# This script activates the virtual environment and launches the application

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}SD Image Viewer Launcher${NC}"
echo "========================"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    
    # Check if python3 is available
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo -e "${RED}Error: Python is not installed or not in PATH${NC}"
        exit 1
    fi
    
    # Create virtual environment
    $PYTHON_CMD -m venv .venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}Virtual environment created.${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if requirements are installed
if [ ! -f ".requirements_installed" ] || [ "requirements.txt" -nt ".requirements_installed" ]; then
    echo -e "${YELLOW}Installing/updating requirements...${NC}"
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to install requirements${NC}"
        exit 1
    fi
    touch .requirements_installed
    echo -e "${GREEN}Requirements installed.${NC}"
fi

# Launch the application
echo -e "${GREEN}Launching SD Image Viewer...${NC}"
python src/main.py "$@"

# Deactivate virtual environment on exit
deactivate
