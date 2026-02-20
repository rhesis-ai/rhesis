#!/bin/bash
# Create a git worktree with symlinked .env files and shared directories
#
# Usage: scripts/create-worktree.sh <name>
# Example: scripts/create-worktree.sh feat/my-feature

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Validate arguments
if [ -z "$1" ]; then
    echo -e "${RED}Error: Missing worktree name${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${GREEN}./rh worktree <name>${NC}"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo -e "  ${BLUE}./rh worktree feat/my-feature${NC}"
    echo -e "  ${BLUE}./rh worktree fix/login-bug${NC}"
    exit 1
fi

NAME="$1"
WORKTREE_DIR="$SOURCE_DIR/../../worktrees/rhesis/$NAME"

echo -e "${CYAN}Creating git worktree: ${WHITE}$NAME${NC}"
echo -e "${PURPLE}========================================${NC}"
echo ""

# Create parent directory
mkdir -p "$(dirname "$WORKTREE_DIR")"

# Create the worktree with a matching branch
echo -e "${YELLOW}Creating worktree...${NC}"
git -C "$SOURCE_DIR" worktree add -b "$NAME" "$WORKTREE_DIR"
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to create worktree${NC}"
    exit 1
fi
echo -e "${GREEN}Worktree created at: ${WHITE}$WORKTREE_DIR${NC}"
echo ""

# Resolve worktree to absolute path (now that it exists)
WORKTREE_DIR="$(cd "$WORKTREE_DIR" && pwd)"

# Track created symlinks for summary
SYMLINKS=()

# Symlink shared directories
echo -e "${YELLOW}Symlinking shared directories...${NC}"
for dir in playground simulations; do
    if [ -d "$SOURCE_DIR/$dir" ]; then
        if ln -s "$SOURCE_DIR/$dir" "$WORKTREE_DIR/$dir" 2>/dev/null; then
            SYMLINKS+=("$dir/ -> $SOURCE_DIR/$dir")
            echo -e "  ${GREEN}${dir}/${NC}"
        else
            echo -e "  ${YELLOW}${dir}/ (failed to create symlink, skipping)${NC}"
        fi
    else
        echo -e "  ${BLUE}${dir}/ (not found in source, skipping)${NC}"
    fi
done
echo ""

# Find and symlink .env files
echo -e "${YELLOW}Symlinking .env files...${NC}"
cd "$SOURCE_DIR" || exit 1

env_count=0

# Find all .env* files, excluding:
# - .env.example (tracked in git)
# - files inside playground/ and simulations/ (covered by dir symlinks)
# - files inside .git/, node_modules/, .venv/
while IFS= read -r env_file; do
    # Get relative path
    rel_path="${env_file#./}"

    # Skip .env.example files
    if [[ "$rel_path" == *".env.example"* ]]; then
        continue
    fi

    # Skip files inside symlinked directories
    if [[ "$rel_path" == playground/* ]] || [[ "$rel_path" == simulations/* ]]; then
        continue
    fi

    # Create parent directory in worktree if needed
    parent_dir="$(dirname "$WORKTREE_DIR/$rel_path")"
    mkdir -p "$parent_dir"

    # Create symlink
    if ln -s "$SOURCE_DIR/$rel_path" "$WORKTREE_DIR/$rel_path" 2>/dev/null; then
        SYMLINKS+=("$rel_path -> $SOURCE_DIR/$rel_path")
        echo -e "  ${GREEN}${rel_path}${NC}"
    else
        echo -e "  ${YELLOW}${rel_path} (failed to create symlink, skipping)${NC}"
    fi
    env_count=$((env_count + 1))
done < <(find . -name '.env*' \
    -not -path './.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/.venv/*' \
    -not -path './playground/*' \
    -not -path './simulations/*' \
    2>/dev/null | sort)

if [ "$env_count" -eq 0 ]; then
    echo -e "  ${BLUE}No .env files found in source, skipping${NC}"
fi

# Summary
echo ""
echo -e "${PURPLE}========================================${NC}"
echo -e "${GREEN}Worktree ready!${NC}"
echo -e "${PURPLE}========================================${NC}"
echo ""
echo -e "${CYAN}Branch:${NC}    ${WHITE}$NAME${NC}"
echo -e "${CYAN}Location:${NC}  ${WHITE}$WORKTREE_DIR${NC}"
echo -e "${CYAN}Symlinks:${NC}  ${WHITE}${#SYMLINKS[@]} created${NC}"
echo ""
echo -e "${YELLOW}To use:${NC}"
echo -e "  ${GREEN}cd $WORKTREE_DIR${NC}"
echo ""
echo -e "${YELLOW}To remove:${NC}"
echo -e "  ${GREEN}git worktree remove $WORKTREE_DIR && git branch -d $NAME${NC}"
echo ""
