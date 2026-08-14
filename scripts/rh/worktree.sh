#!/bin/bash
# Manage git worktrees with symlinked .env files and shared directories
#
# Reached via `./rh worktree`, which runs this as a subprocess. Also runnable
# directly:
#   scripts/rh/worktree.sh <name>              Create a new worktree
#   scripts/rh/worktree.sh --init              Set up the worktree you are in
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
    echo -e "  ${GREEN}./rh worktree --init${NC}            Set up the worktree you are standing in"
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
    step "${GREEN}--init${NC}${YELLOW} gives all of that to a worktree made with a bare"
    step "${GREEN}git worktree add${NC}${YELLOW}. Run it from inside that worktree — it finds the main"
    step "checkout on its own. Without it the worktree has no .rhesis-ports, so it"
    step "shares the main checkout's ports and containers, and ${GREEN}./rh dev clean${NC}${YELLOW} there"
    step "would drop main's dev database."
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

port_offset_of() {
    local ports_file="$1/.rhesis-ports"
    [ -f "$ports_file" ] || return 0
    grep -m1 '^RHESIS_PORT_OFFSET=' "$ports_file" | cut -d= -f2 | tr -d " \"'\r"
}

# The main checkout owns the .env files and the shared directories every
# worktree links back to. --git-common-dir resolves to its .git from anywhere in
# the repo, including from inside a worktree.
main_checkout_of() {
    local common
    common=$(git -C "$1" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 1
    [ -n "$common" ] || return 1
    dirname "$common"
}

is_registered_worktree() {
    git -C "$SOURCE_DIR" worktree list --porcelain 2>/dev/null | grep -qxF "worktree $1"
}

rewrite_backend_env_ports() {
    local file="$1"
    local offset="$2"
    set_env_var "$file" PORT "$(dev_port_for backend "$offset")"
    set_env_var "$file" DB_PORT "$(dev_port_for postgres "$offset")"
    set_env_url_port "$file" BROKER_URL "$(dev_port_for redis "$offset")"
    set_env_url_port "$file" CELERY_RESULT_BACKEND "$(dev_port_for redis "$offset")"
    # The backend's CORS allowlist is derived from this, so it must track the worktree's frontend
    set_env_var "$file" FRONTEND_URL "http://localhost:$(dev_port_for frontend "$offset")"
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

        # Worktrees predating WORKTREE_OWN_ENV_FILES have these symlinked into the
        # main checkout. set_env_var appends through the link, so it would add
        # FRONTEND_URL to main's own .env, and BSD sed -i then refuses the link
        # ("in-place editing only works for regular files") — leaving the worktree
        # on main's ports while the summary says it's ready. Replace with a copy.
        if [ -L "$dest" ]; then
            rm -f "$dest"
            echo -e "  ${BLUE}${rel} was symlinked to the main checkout — replacing with a copy${NC}"
        fi

        # --init may find a worktree that already has its own; those keep their
        # contents and only get their ports shifted.
        local action="copied"
        if [ -f "$dest" ]; then
            action="kept"
        elif [ -f "$src" ]; then
            mkdir -p "$(dirname "$dest")"
            cp "$src" "$dest"
        else
            echo -e "  ${BLUE}${rel} (not in source — run ./rh dev init in the worktree)${NC}"
            continue
        fi

        case "$rel" in
            apps/frontend/*) rewrite_frontend_env_ports "$dest" "$offset" ;;
            *) rewrite_backend_env_ports "$dest" "$offset" ;;
        esac
        echo -e "  ${GREEN}${rel}${NC} (${action}, ports +${offset})"
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
# Provisioning: everything a worktree needs beyond the checkout itself
# ============================================================================

# Puts the link in place and echoes what happened. Returns 0 only when it
# created one, so callers can count. A real file or directory in the way is left
# alone — in a gitignored path it may be the only copy.
link_into_worktree() {
    local src="$1" dest="$2" label="$3"

    if [ -L "$dest" ]; then
        if [ "$(readlink "$dest")" = "$src" ]; then
            echo -e "  ${BLUE}${label} (already linked)${NC}"
            return 1
        fi
        if ln -sfn "$src" "$dest" 2>/dev/null; then
            echo -e "  ${GREEN}${label}${NC} (relinked)"
            return 0
        fi
    elif [ -e "$dest" ]; then
        echo -e "  ${YELLOW}${label} (real file in the worktree, left alone)${NC}"
        return 1
    fi

    mkdir -p "$(dirname "$dest")"
    if ln -s "$src" "$dest" 2>/dev/null; then
        echo -e "  ${GREEN}${label}${NC}"
        return 0
    fi
    echo -e "  ${YELLOW}${label} (failed to create symlink, skipping)${NC}"
    return 1
}

# Idempotent, so --init can run it over a worktree that already has some of
# this. $SOURCE_DIR must be the main checkout — every link points back into it.
worktree_provision() {
    local worktree_dir="$1"
    local name="$2"

    # Every ./rh dev command in the worktree reads this file for its ports
    echo -e "${YELLOW}Allocating ports...${NC}"
    # The recorded name wins: it's what the existing containers, volumes and tmux
    # session are prefixed with, so renaming here would strand them.
    local wt_name offset existing
    wt_name=$(worktree_name_of "$worktree_dir")
    if [ -z "$wt_name" ]; then
        wt_name=$(sanitize_worktree_name "$name")
    elif [ "$wt_name" != "$(sanitize_worktree_name "$name")" ]; then
        warn "Keeping the recorded name ${wt_name} — renaming would orphan its containers"
    fi

    # Offset 0 is the main checkout's block. A worktree carrying it — what the
    # WorktreeCreate hook writes when allocation failed — shares main's ports,
    # so reallocate rather than keep it.
    existing=$(port_offset_of "$worktree_dir")
    if [ -z "$existing" ] || [ "$existing" = "0" ]; then
        offset=$(allocate_port_offset "$worktree_dir") || exit 1
    elif offset_taken_by_other "$worktree_dir" "$existing"; then
        warn "Offset ${existing} in .rhesis-ports is claimed by another worktree — reallocating"
        offset=$(allocate_port_offset "$worktree_dir") || exit 1
    else
        offset="$existing"
        echo -e "${BLUE}Keeping the offset already in .rhesis-ports${NC}"
    fi
    printf 'RHESIS_PORT_OFFSET=%s\nRHESIS_WORKTREE_NAME=%s\n' "$offset" "$wt_name" > "$worktree_dir/.rhesis-ports"
    echo -e "${GREEN}Offset ${WHITE}${offset}${GREEN}, dev names prefixed ${WHITE}$(dev_prefix_for "$wt_name")${NC}"
    echo ""

    # Track created symlinks for summary
    local symlink_count=0

    # Symlink shared directories. These are gitignored, so a worktree that got its
    # own empty copy would lose whatever was written there when it's removed.
    echo -e "${YELLOW}Symlinking shared directories...${NC}"
    for dir in playground simulations domain.local; do
        if [ -d "$SOURCE_DIR/$dir" ]; then
            link_into_worktree "$SOURCE_DIR/$dir" "$worktree_dir/$dir" "${dir}/" &&
                symlink_count=$((symlink_count + 1))
        else
            echo -e "  ${BLUE}${dir}/ (not found in source, skipping)${NC}"
        fi
    done
    echo ""

    # Find and symlink .env files
    echo -e "${YELLOW}Symlinking .env files...${NC}"
    cd "$SOURCE_DIR" || exit 1

    local env_count=0

    # Skips .env.example (tracked), the directories already symlinked above, and
    # the two port-bearing dev files.
    while IFS= read -r env_file; do
        # Get relative path
        local rel_path="${env_file#./}"

        # Skip .env.example files
        if [[ "$rel_path" == *".env.example"* ]]; then
            continue
        fi

        # Skip files inside symlinked directories
        if [[ "$rel_path" == playground/* ]] || [[ "$rel_path" == simulations/* ]] ||
            [[ "$rel_path" == domain.local/* ]]; then
            continue
        fi

        # Skip the port-bearing dev files; copied with their own ports below
        if [[ " $WORKTREE_OWN_ENV_FILES " == *" $rel_path "* ]]; then
            continue
        fi

        link_into_worktree "$SOURCE_DIR/$rel_path" "$worktree_dir/$rel_path" "$rel_path" &&
            symlink_count=$((symlink_count + 1))
        env_count=$((env_count + 1))
    # -prune, not -not -path: filtering the output still walks every
    # node_modules and .venv, which is ~650k files here for 10 hits.
    done < <(find . \
        \( -name .git -o -name node_modules -o -name .venv \
           -o -path ./playground -o -path ./simulations -o -path ./domain.local \) -prune \
        -o -name '.env*' -print \
        2>/dev/null | sort)

    if [ "$env_count" -eq 0 ]; then
        echo -e "  ${BLUE}No .env files found in source, skipping${NC}"
    fi
    echo ""

    echo -e "${YELLOW}Creating dev env files...${NC}"
    create_worktree_env_files "$worktree_dir" "$offset"
    echo ""

    # Symlink the gitignored Claude Code config. CLAUDE.local.md is what points the
    # agent skills at .claude/skills.local, so a worktree missing either one silently
    # falls back to the skills' own defaults.
    echo -e "${YELLOW}Symlinking Claude Code config...${NC}"
    for rel in .claude/settings.local.json .claude/skills.local CLAUDE.local.md; do
        if [ ! -e "$SOURCE_DIR/$rel" ]; then
            echo -e "  ${BLUE}${rel} not found in source, skipping${NC}"
            continue
        fi
        link_into_worktree "$SOURCE_DIR/$rel" "$worktree_dir/$rel" "$rel" &&
            symlink_count=$((symlink_count + 1))
    done

    local branch
    branch=$(git -C "$worktree_dir" branch --show-current 2>/dev/null)

    # Summary
    echo ""
    echo -e "${PURPLE}========================================${NC}"
    echo -e "${GREEN}Worktree ready!${NC}"
    echo -e "${PURPLE}========================================${NC}"
    echo ""
    echo -e "${CYAN}Branch:${NC}    ${WHITE}${branch:-detached HEAD}${NC}"
    echo -e "${CYAN}Location:${NC}  ${WHITE}$worktree_dir${NC}"
    echo -e "${CYAN}Symlinks:${NC}  ${WHITE}${symlink_count} created${NC}"
    echo -e "${CYAN}Offset:${NC}    ${WHITE}${offset}${NC}"
    echo -e "${CYAN}Ports:${NC}     ${WHITE}postgres $(dev_port_for postgres "$offset"), redis $(dev_port_for redis "$offset"), backend $(dev_port_for backend "$offset"), frontend $(dev_port_for frontend "$offset"), flower $(dev_port_for flower "$offset")${NC}"
    echo -e "${CYAN}Prefix:${NC}    ${WHITE}$(dev_prefix_for "$wt_name")${NC} (containers, volumes, tmux)"
    echo ""

    # --load and --remove address a worktree as $WORKTREES_BASE/<name>, so one
    # outside that directory can't be reached by name.
    local base_resolved
    base_resolved="$(cd "$WORKTREES_BASE" 2>/dev/null && pwd)"
    if [ -n "$base_resolved" ] && [ "$worktree_dir" = "$base_resolved/$name" ]; then
        echo -e "${YELLOW}To use:${NC}"
        echo -e "  ${GREEN}./rh worktree $name --load${NC}"
        echo ""
        echo -e "${YELLOW}To remove:${NC}"
        echo -e "  ${GREEN}./rh worktree $name --remove${NC}"
    else
        warn "This worktree is outside $base_resolved, so ./rh worktree --load and"
        step "   --remove can't find it by name. Remove it with git worktree remove,"
        step "   and stop its stack first with ./rh dev clean from inside it."
    fi
    echo ""
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
    if ! git -C "$SOURCE_DIR" worktree add -b "$name" "$worktree_dir"; then
        die "Error: Failed to create worktree"
    fi
    echo -e "${GREEN}Worktree created at: ${WHITE}$worktree_dir${NC}"
    echo ""

    # Resolve worktree to absolute path (now that it exists)
    worktree_dir="$(cd "$worktree_dir" && pwd)"

    worktree_provision "$worktree_dir" "$name"
}

# ============================================================================
# --init: provision a worktree that already exists
# ============================================================================

# Named for the summary line and the container prefix. A worktree under
# WORKTREES_BASE keeps its path there, so --load and --remove still find it;
# anything else falls back to the directory name.
worktree_name_from_path() {
    local worktree_dir="$1" base_resolved
    base_resolved="$(cd "$WORKTREES_BASE" 2>/dev/null && pwd)"
    if [ -n "$base_resolved" ] && [ "${worktree_dir#"$base_resolved"/}" != "$worktree_dir" ]; then
        echo "${worktree_dir#"$base_resolved"/}"
    else
        basename "$worktree_dir"
    fi
}

# Run from inside the worktree, or from the main checkout with a name. A bare
# `git worktree add` leaves a checkout with no .rhesis-ports, which means offset
# 0 and the rhesis-dev prefix — it shares the main checkout's ports, containers
# and volumes, so ./rh dev clean there would drop main's dev database.
worktree_init() {
    local name="${1:-}"
    local worktree_dir

    # Inside a worktree, SCRIPT_DIR is the worktree itself, so every source path
    # has to be re-derived from the main checkout or the links point at nothing.
    SOURCE_DIR=$(main_checkout_of "$PWD") ||
        die "Not inside a git checkout" "Run this from inside the worktree you want to set up."
    WORKTREES_BASE="$SOURCE_DIR/../../worktrees/rhesis"

    if [ -n "$name" ]; then
        [ -d "$WORKTREES_BASE/$name" ] ||
            die "Worktree not found at $WORKTREES_BASE/$name" "See them all: ./rh worktree --list"
        worktree_dir="$(cd "$WORKTREES_BASE/$name" && pwd)"
    else
        worktree_dir=$(git rev-parse --show-toplevel 2>/dev/null) ||
            die "Not inside a git checkout"
    fi

    if [ "$worktree_dir" = "$SOURCE_DIR" ]; then
        die "$worktree_dir is the main checkout, not a worktree" \
            "It already owns the shared .env files and the default dev ports." \
            "Create a worktree with: ./rh worktree <name>"
    fi

    is_registered_worktree "$worktree_dir" ||
        die "$worktree_dir is not a registered worktree of $SOURCE_DIR" \
            "Register it first: git -C $SOURCE_DIR worktree add <path> <branch>"

    [ -n "$name" ] || name=$(worktree_name_from_path "$worktree_dir")

    if [ -z "$(sanitize_worktree_name "$name")" ]; then
        die "Cannot derive a usable name from '$name'" \
            "It must contain at least one letter or digit — an empty name maps to" \
            "the main checkout's rhesis-dev containers and volumes."
    fi

    echo -e "${CYAN}Setting up existing worktree: ${WHITE}$name${NC}"
    echo -e "${PURPLE}========================================${NC}"
    echo -e "${CYAN}Main checkout: ${WHITE}$SOURCE_DIR${NC}"
    echo -e "${CYAN}Worktree:      ${WHITE}$worktree_dir${NC}"
    echo ""

    worktree_provision "$worktree_dir" "$name"
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
    # No name: the worktree is wherever this was run from. `--init <name>` is the
    # documented `<name> --init` transposed, which is an easy typo, so take it too.
    --init)
        case "${2:-}" in
            -*|"") worktree_init "" ;;
            *) worktree_init "$2" ;;
        esac
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
    "--init")
        worktree_init "$NAME"
        ;;
    "create"|"")
        worktree_create "$NAME"
        ;;
    *)
        show_usage "Unknown option '$ACTION'"
        ;;
esac
