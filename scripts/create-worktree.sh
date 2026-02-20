#!/bin/bash
# Manage git worktrees with symlinked .env files and shared directories
#
# Usage:
#   scripts/create-worktree.sh <name>              Create a new worktree
#   scripts/create-worktree.sh <name> --remove      Remove a worktree and its branch
#   scripts/create-worktree.sh <name> --load        Launch shell in worktree
#   scripts/create-worktree.sh --list               List all worktrees

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
WORKTREES_BASE="$SOURCE_DIR/../../worktrees/rhesis"

# ============================================================================
# Usage
# ============================================================================

show_usage() {
    local msg="${1:-Missing worktree name}"
    echo -e "${RED}Error: $msg${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${GREEN}./rh worktree <name>${NC}            Create a new worktree"
    echo -e "  ${GREEN}./rh worktree <name> --remove${NC}   Remove worktree and branch"
    echo -e "  ${GREEN}./rh worktree <name> --load${NC}     Launch shell in worktree"
    echo -e "  ${GREEN}./rh worktree --list${NC}            List all worktrees"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo -e "  ${BLUE}./rh worktree feat/my-feature${NC}"
    echo -e "  ${BLUE}./rh worktree feat/my-feature --load${NC}"
    echo -e "  ${BLUE}./rh worktree feat/my-feature --remove${NC}"
    echo -e "  ${BLUE}./rh worktree --list${NC}"
    exit 1
}

# ============================================================================
# --list: show all worktrees
# ============================================================================

worktree_list() {
    echo -e "${CYAN}Git Worktrees${NC}"
    echo -e "${PURPLE}========================================${NC}"
    echo ""
    git -C "$SOURCE_DIR" worktree list
    echo ""
}

# ============================================================================
# --remove: remove worktree and delete branch
# ============================================================================

worktree_remove() {
    local name="$1"
    local worktree_dir="$WORKTREES_BASE/$name"

    # Resolve to absolute path if it exists
    if [ -d "$worktree_dir" ]; then
        worktree_dir="$(cd "$worktree_dir" && pwd)"
    else
        echo -e "${RED}Error: Worktree not found at ${WHITE}$worktree_dir${NC}"
        exit 1
    fi

    echo -e "${CYAN}Removing worktree: ${WHITE}$name${NC}"
    echo -e "${PURPLE}========================================${NC}"
    echo ""

    echo -e "${YELLOW}Removing worktree directory...${NC}"
    git -C "$SOURCE_DIR" worktree remove --force "$worktree_dir"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to remove worktree${NC}"
        exit 1
    fi
    echo -e "${GREEN}Worktree removed${NC}"

    echo -e "${YELLOW}Deleting branch...${NC}"
    git -C "$SOURCE_DIR" branch -d "$name" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Branch ${WHITE}$name${GREEN} deleted${NC}"
    else
        echo -e "${BLUE}Branch ${WHITE}$name${BLUE} not found or not fully merged (kept)${NC}"
    fi

    echo ""
    echo -e "${GREEN}Done!${NC}"
    echo ""
}

# ============================================================================
# --load: launch shell in worktree
# ============================================================================

worktree_load() {
    local name="$1"
    local worktree_dir="$WORKTREES_BASE/$name"

    if [ ! -d "$worktree_dir" ]; then
        echo -e "${RED}Error: Worktree not found at ${WHITE}$worktree_dir${NC}"
        echo ""
        echo -e "${YELLOW}Available worktrees:${NC}"
        git -C "$SOURCE_DIR" worktree list
        echo ""
        exit 1
    fi

    # Resolve to absolute path
    worktree_dir="$(cd "$worktree_dir" && pwd)"

    # Pick a random prompt color for this worktree shell
    local colors=(yellow blue magenta cyan white)
    local color=${colors[$((RANDOM % ${#colors[@]}))]}
    export RHESIS_WORKTREE="$name"
    export RHESIS_WORKTREE_COLOR="$color"

    echo -e "${CYAN}Worktree: ${WHITE}$name${NC}"
    echo -e "${CYAN}Location: ${WHITE}$worktree_dir${NC}"
    echo -e "${BLUE}Launching shell in worktree (exit to return)${NC}"
    echo ""
    cd "$worktree_dir" && exec "$SHELL"
}

# ============================================================================
# create: default action — create worktree with symlinks
# ============================================================================

worktree_create() {
    local name="$1"
    local worktree_dir="$WORKTREES_BASE/$name"

    echo -e "${CYAN}Creating git worktree: ${WHITE}$name${NC}"
    echo -e "${PURPLE}========================================${NC}"
    echo ""

    # Create parent directory
    mkdir -p "$(dirname "$worktree_dir")"

    # Create the worktree with a matching branch
    echo -e "${YELLOW}Creating worktree...${NC}"
    git -C "$SOURCE_DIR" worktree add -b "$name" "$worktree_dir"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create worktree${NC}"
        exit 1
    fi
    echo -e "${GREEN}Worktree created at: ${WHITE}$worktree_dir${NC}"
    echo ""

    # Resolve worktree to absolute path (now that it exists)
    worktree_dir="$(cd "$worktree_dir" && pwd)"

    # Track created symlinks for summary
    local symlink_count=0

    # Symlink shared directories
    echo -e "${YELLOW}Symlinking shared directories...${NC}"
    for dir in playground simulations; do
        if [ -d "$SOURCE_DIR/$dir" ]; then
            if ln -s "$SOURCE_DIR/$dir" "$worktree_dir/$dir" 2>/dev/null; then
                symlink_count=$((symlink_count + 1))
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

    local env_count=0

    # Find all .env* files, excluding:
    # - .env.example (tracked in git)
    # - files inside playground/ and simulations/ (covered by dir symlinks)
    # - files inside .git/, node_modules/, .venv/
    while IFS= read -r env_file; do
        # Get relative path
        local rel_path="${env_file#./}"

        # Skip .env.example files
        if [[ "$rel_path" == *".env.example"* ]]; then
            continue
        fi

        # Skip files inside symlinked directories
        if [[ "$rel_path" == playground/* ]] || [[ "$rel_path" == simulations/* ]]; then
            continue
        fi

        # Create parent directory in worktree if needed
        local parent_dir
        parent_dir="$(dirname "$worktree_dir/$rel_path")"
        mkdir -p "$parent_dir"

        # Create symlink
        if ln -s "$SOURCE_DIR/$rel_path" "$worktree_dir/$rel_path" 2>/dev/null; then
            symlink_count=$((symlink_count + 1))
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
    echo -e "${CYAN}Branch:${NC}    ${WHITE}$name${NC}"
    echo -e "${CYAN}Location:${NC}  ${WHITE}$worktree_dir${NC}"
    echo -e "${CYAN}Symlinks:${NC}  ${WHITE}${symlink_count} created${NC}"
    echo ""
    echo -e "${YELLOW}To use:${NC}"
    echo -e "  ${GREEN}./rh worktree $name --load${NC}"
    echo ""
    echo -e "${YELLOW}To remove:${NC}"
    echo -e "  ${GREEN}./rh worktree $name --remove${NC}"
    echo ""
}

# ============================================================================
# Argument parsing
# ============================================================================

# Handle --list anywhere in args
if [ "$1" = "--list" ] || [ "$2" = "--list" ]; then
    worktree_list
    exit 0
fi

# All other commands require a name
if [ -z "$1" ]; then
    show_usage
fi

NAME="$1"
ACTION="${2:-create}"

# Validate name: reject path traversal, absolute paths, and leading dashes
if [[ "$NAME" == /* ]] || [[ "$NAME" == *..* ]] || [[ "$NAME" == -* ]]; then
    show_usage "Invalid worktree name '$NAME'. Name must not contain '..', start with '/', or start with '-'"
fi

case "$ACTION" in
    "--remove")
        worktree_remove "$NAME"
        ;;
    "--load")
        worktree_load "$NAME"
        ;;
    "create"|"")
        worktree_create "$NAME"
        ;;
    *)
        show_usage "Unknown option '$ACTION'"
        ;;
esac
