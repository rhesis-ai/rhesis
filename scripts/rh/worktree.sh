#!/bin/bash
# Manage git worktrees with symlinked .env files and shared directories
#
# Reached via `./rh worktree`, which runs this as a subprocess. Also runnable
# directly:
#   scripts/rh/worktree.sh <name>              Create a new worktree
#   scripts/rh/worktree.sh <name> --remove     Remove a worktree and its branch
#   scripts/rh/worktree.sh <name> --load       Launch shell in worktree
#   scripts/rh/worktree.sh --list              List all worktrees

# Colors and shared helpers. common.sh sets SCRIPT_DIR to the repository root,
# which is what this script calls SOURCE_DIR.
RH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for wt_lib in common ports portalloc; do
    # shellcheck source=/dev/null
    source "$RH_LIB_DIR/$wt_lib.sh" || {
        echo "❌ Failed to load scripts/rh/$wt_lib.sh" >&2
        exit 1
    }
done
unset wt_lib

SOURCE_DIR="$SCRIPT_DIR"

# These carry ports, so a worktree gets its own copies instead of symlinks.
WORKTREE_OWN_ENV_FILES="apps/backend/.env apps/frontend/.env.local"
WORKTREES_BASE="$SOURCE_DIR/../../worktrees/rhesis"

# ============================================================================
# Usage
# ============================================================================

show_worktree_help() {
    head1 "Worktree Commands:"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${GREEN}./rh worktree <name>${NC}            Create a worktree with its own dev ports"
    echo -e "  ${GREEN}./rh worktree <name> --remove${NC}   Remove worktree, its dev containers, and branch"
    echo -e "  ${GREEN}./rh worktree <name> --load${NC}     Launch shell in worktree"
    echo -e "  ${GREEN}./rh worktree --list${NC}            List all worktrees"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo -e "  ${BLUE}./rh worktree feat/my-feature${NC}"
    echo -e "  ${BLUE}./rh worktree feat/my-feature --load${NC}"
    echo -e "  ${BLUE}./rh worktree feat/my-feature --remove${NC}"
    echo -e "  ${BLUE}./rh worktree --list${NC}"
    echo ""
    step "A new worktree branches from your current HEAD (committed work only), gets"
    step "shared .env symlinks, and a free block of dev ports recorded in"
    step ".rhesis-ports at its root. Inside it, ${GREEN}./rh dev up${NC}${YELLOW} and the other dev"
    step "commands use those ports — run ${GREEN}./rh dev status${NC}${YELLOW} to see them."
    echo ""
}

show_usage() {
    echo -e "${RED}Error: ${1:-Missing worktree name}${NC}"
    echo ""
    show_worktree_help
    exit 1
}

# ============================================================================
# Per-worktree dev environment: ports, env files, containers
# ============================================================================

# Lands in docker and tmux names, so keep it to lowercase, digits and dashes.
sanitize_worktree_name() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E -e 's/[^a-z0-9]+/-/g' -e 's/^-+//' -e 's/-+$//'
}

worktree_name_of() {
    local ports_file="$1/.rhesis-ports"
    [ -f "$ports_file" ] || return 0
    grep -m1 '^RHESIS_WORKTREE_NAME=' "$ports_file" | cut -d= -f2 | tr -d " \"'\r"
}

rewrite_backend_env_ports() {
    local file="$1"
    local offset="$2"
    set_env_var "$file" PORT "$(dev_port_for backend "$offset")"
    set_env_var "$file" DB_PORT "$(dev_port_for postgres "$offset")"
    set_env_url_port "$file" BROKER_URL "$(dev_port_for redis "$offset")"
    set_env_url_port "$file" CELERY_RESULT_BACKEND "$(dev_port_for redis "$offset")"
}

rewrite_frontend_env_ports() {
    local file="$1"
    local offset="$2"
    set_env_var "$file" PORT "$(dev_port_for frontend "$offset")"
    set_env_url_port "$file" API_BASE_URL "$(dev_port_for backend "$offset")"
    set_env_url_port "$file" BACKEND_URL "$(dev_port_for backend "$offset")"
    set_env_url_port "$file" FRONTEND_URL "$(dev_port_for frontend "$offset")"
}

# Copied rather than symlinked, then shifted onto this worktree's ports. Copying
# keeps the secrets and the ./rh dev init marker that ./rh dev up requires.
create_worktree_env_files() {
    local worktree_dir="$1"
    local offset="$2"
    local rel src dest

    for rel in $WORKTREE_OWN_ENV_FILES; do
        src="$SOURCE_DIR/$rel"
        dest="$worktree_dir/$rel"

        if [ ! -f "$src" ]; then
            echo -e "  ${BLUE}${rel} (not in source — run ./rh dev init in the worktree)${NC}"
            continue
        fi

        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        case "$rel" in
            apps/frontend/*) rewrite_frontend_env_ports "$dest" "$offset" ;;
            *) rewrite_backend_env_ports "$dest" "$offset" ;;
        esac
        echo -e "  ${GREEN}${rel}${NC} (copied, ports +${offset})"
    done
}

# Containers outlive the directory otherwise, holding this worktree's ports.
remove_worktree_stack() {
    local worktree_dir="$1"
    local wt_name
    wt_name=$(worktree_name_of "$worktree_dir")
    [ -n "$wt_name" ] || return 0

    if command -v tmux &>/dev/null; then
        tmux kill-session -t "rhesis-$wt_name" 2>/dev/null || true
    fi

    local prefix
    prefix=$(dev_prefix_for "$wt_name")

    if ! docker info >/dev/null 2>&1; then
        warn "Docker is not running — leaving ${prefix}-* containers and volumes behind"
        return 0
    fi

    step "Removing dev containers for ${wt_name}..."
    docker stop "${prefix}-postgres" "${prefix}-redis" 2>/dev/null || true
    docker rm "${prefix}-postgres" "${prefix}-redis" 2>/dev/null || true
    docker volume rm "${prefix}-postgres-data" "${prefix}-redis-data" 2>/dev/null || true

    local leftover
    leftover=$(dev_volumes_for_prefix "$prefix")
    if [ -n "$leftover" ]; then
        echo "$leftover" | xargs docker volume rm 2>/dev/null || true
    fi
    echo -e "${GREEN}Dev containers and volumes removed${NC}"
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

    remove_worktree_stack "$worktree_dir"

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

    # Every ./rh dev command in the worktree reads this file for its ports
    echo -e "${YELLOW}Allocating ports...${NC}"
    local wt_name offset
    wt_name=$(sanitize_worktree_name "$name")
    offset=$(allocate_port_offset) || exit 1
    printf 'RHESIS_PORT_OFFSET=%s\nRHESIS_WORKTREE_NAME=%s\n' "$offset" "$wt_name" > "$worktree_dir/.rhesis-ports"
    echo -e "${GREEN}Offset ${WHITE}${offset}${GREEN}, dev names prefixed ${WHITE}$(dev_prefix_for "$wt_name")${NC}"
    echo ""

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

    # Skips .env.example (tracked), playground/ and simulations/ (already
    # symlinked as directories), and the two port-bearing dev files.
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

        # Skip the port-bearing dev files; copied with their own ports below
        if [[ " $WORKTREE_OWN_ENV_FILES " == *" $rel_path "* ]]; then
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
    # -prune, not -not -path: filtering the output still walks every
    # node_modules and .venv, which is ~650k files here for 10 hits.
    done < <(find . \
        \( -name .git -o -name node_modules -o -name .venv \
           -o -path ./playground -o -path ./simulations \) -prune \
        -o -name '.env*' -print \
        2>/dev/null | sort)

    if [ "$env_count" -eq 0 ]; then
        echo -e "  ${BLUE}No .env files found in source, skipping${NC}"
    fi
    echo ""

    echo -e "${YELLOW}Creating dev env files...${NC}"
    create_worktree_env_files "$worktree_dir" "$offset"
    echo ""

    # Symlink Claude Code settings.local.json
    echo -e "${YELLOW}Symlinking Claude Code settings...${NC}"
    if [ -f "$SOURCE_DIR/.claude/settings.local.json" ]; then
        mkdir -p "$worktree_dir/.claude"
        if [ -f "$worktree_dir/.claude/settings.local.json" ] && [ ! -L "$worktree_dir/.claude/settings.local.json" ]; then
            rm "$worktree_dir/.claude/settings.local.json"
        fi
        if ln -sf "$SOURCE_DIR/.claude/settings.local.json" "$worktree_dir/.claude/settings.local.json" 2>/dev/null; then
            symlink_count=$((symlink_count + 1))
            echo -e "  ${GREEN}.claude/settings.local.json${NC}"
        else
            echo -e "  ${YELLOW}.claude/settings.local.json (failed to create symlink, skipping)${NC}"
        fi
    else
        echo -e "  ${BLUE}.claude/settings.local.json not found in source, skipping${NC}"
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
    echo -e "${CYAN}Offset:${NC}    ${WHITE}${offset}${NC}"
    echo -e "${CYAN}Ports:${NC}     ${WHITE}postgres $(dev_port_for postgres "$offset"), redis $(dev_port_for redis "$offset"), backend $(dev_port_for backend "$offset"), frontend $(dev_port_for frontend "$offset"), flower $(dev_port_for flower "$offset")${NC}"
    echo -e "${CYAN}Prefix:${NC}    ${WHITE}$(dev_prefix_for "$wt_name")${NC} (containers, volumes, tmux)"
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

# "help" before anything else: it would otherwise be taken as a worktree name.
case "${1:-}" in
    ""|help|--help|-h)
        show_worktree_help
        exit 0
        ;;
esac

# Handle --list anywhere in args
if [ "$1" = "--list" ] || [ "$2" = "--list" ]; then
    worktree_list
    exit 0
fi

NAME="$1"
ACTION="${2:-create}"

# Validate name: reject path traversal, absolute paths, and leading dashes
if [[ "$NAME" == /* ]] || [[ "$NAME" == *..* ]] || [[ "$NAME" == -* ]]; then
    show_usage "Invalid worktree name '$NAME'. Name must not contain '..', start with '/', or start with '-'"
fi

# A name with nothing alphanumeric in it (git allows '_', '...', '@@') sanitizes
# to the empty string, which dev_prefix_for maps to the main checkout's
# rhesis-dev containers and volumes — so ./rh dev clean in that worktree would
# drop main's dev database.
if [ -z "$(sanitize_worktree_name "$NAME")" ]; then
    show_usage "Invalid worktree name '$NAME'. Name must contain at least one letter or digit"
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
