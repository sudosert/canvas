#!/bin/bash
# Git Push Helper Script
# Automates git add, commit, and push with interactive commit message input

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

echo -e "${BLUE}Git Push Helper${NC}"
echo "==============="
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not a git repository${NC}"
    exit 1
fi

# Show current branch
CURRENT_BRANCH=$(git branch --show-current)
echo -e "Current branch: ${GREEN}$CURRENT_BRANCH${NC}"
echo ""

# Show git status
echo -e "${YELLOW}Git Status:${NC}"
git status -s
echo ""

# Check if there are changes to commit
if [ -z "$(git status -s)" ]; then
    echo -e "${YELLOW}No changes to commit.${NC}"
    
    # Ask if user wants to push anyway
    read -p "Do you want to push current branch anyway? (y/n): " PUSH_ANYWAY
    if [[ ! "$PUSH_ANYWAY" =~ ^[Yy]$ ]]; then
        echo "Exiting..."
        exit 0
    fi
    
    # Push without committing
    echo ""
    echo -e "${BLUE}Pushing to remote...${NC}"
    if git push origin "$CURRENT_BRANCH"; then
        echo -e "${GREEN}✓ Push successful!${NC}"
    else
        echo -e "${RED}✗ Push failed${NC}"
        exit 1
    fi
    exit 0
fi

# Ask what to add
echo -e "${YELLOW}What would you like to add?${NC}"
echo "1) Add all changes (git add .)"
echo "2) Add specific files"
echo "3) Add interactively (git add -p)"
echo "4) Cancel"
read -p "Select option (1-4): " ADD_OPTION

case $ADD_OPTION in
    1)
        echo -e "${BLUE}Adding all changes...${NC}"
        git add .
        ;;
    2)
        echo ""
        echo -e "${YELLOW}Modified files:${NC}"
        git status -s
        echo ""
        read -p "Enter files to add (space-separated, or '.' for all): " FILES
        if [ -z "$FILES" ]; then
            echo -e "${RED}No files specified. Exiting.${NC}"
            exit 1
        fi
        git add $FILES
        ;;
    3)
        echo -e "${BLUE}Starting interactive add...${NC}"
        git add -p
        ;;
    4)
        echo "Cancelled."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option. Exiting.${NC}"
        exit 1
        ;;
esac

# Show what's staged
echo ""
echo -e "${YELLOW}Staged changes:${NC}"
git diff --cached --stat
echo ""

# Ask for commit message type
echo -e "${YELLOW}Select commit type:${NC}"
echo "1) feat:     New feature"
echo "2) fix:      Bug fix"
echo "3) docs:     Documentation changes"
echo "4) style:    Code style changes (formatting, etc)"
echo "5) refactor: Code refactoring"
echo "6) test:     Adding or updating tests"
echo "7) chore:    Maintenance tasks"
echo "8) custom:   Enter custom commit message"
read -p "Select option (1-8): " COMMIT_TYPE

case $COMMIT_TYPE in
    1) TYPE_PREFIX="feat: " ;;
    2) TYPE_PREFIX="fix: " ;;
    3) TYPE_PREFIX="docs: " ;;
    4) TYPE_PREFIX="style: " ;;
    5) TYPE_PREFIX="refactor: " ;;
    6) TYPE_PREFIX="test: " ;;
    7) TYPE_PREFIX="chore: " ;;
    8) TYPE_PREFIX="" ;;
    *) 
        echo -e "${RED}Invalid option. Using custom message.${NC}"
        TYPE_PREFIX=""
        ;;
esac

# Get commit message
echo ""
read -p "Enter commit message: " COMMIT_MESSAGE

if [ -z "$COMMIT_MESSAGE" ]; then
    echo -e "${RED}Commit message cannot be empty. Exiting.${NC}"
    exit 1
fi

FULL_MESSAGE="${TYPE_PREFIX}${COMMIT_MESSAGE}"

# Confirm commit
echo ""
echo -e "${YELLOW}Commit message:${NC} $FULL_MESSAGE"
read -p "Proceed with commit? (y/n): " CONFIRM

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Commit
echo -e "${BLUE}Committing...${NC}"
if git commit -m "$FULL_MESSAGE"; then
    echo -e "${GREEN}✓ Commit successful!${NC}"
else
    echo -e "${RED}✗ Commit failed${NC}"
    exit 1
fi

# Ask about pushing
echo ""
read -p "Push to origin/$CURRENT_BRANCH? (y/n): " PUSH_CONFIRM

if [[ "$PUSH_CONFIRM" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Pushing to origin/$CURRENT_BRANCH...${NC}"
    if git push origin "$CURRENT_BRANCH"; then
        echo -e "${GREEN}✓ Push successful!${NC}"
    else
        echo -e "${RED}✗ Push failed${NC}"
        
        # Offer to force push if regular push failed
        read -p "Try force push? (y/n): " FORCE_PUSH
        if [[ "$FORCE_PUSH" =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Force pushing...${NC}"
            if git push origin "$CURRENT_BRANCH" --force; then
                echo -e "${GREEN}✓ Force push successful!${NC}"
            else
                echo -e "${RED}✗ Force push failed${NC}"
                exit 1
            fi
        fi
    fi
else
    echo "Changes committed but not pushed."
    echo -e "${YELLOW}To push later, run:${NC} git push origin $CURRENT_BRANCH"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
