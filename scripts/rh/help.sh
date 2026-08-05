#!/bin/bash
# Help screens for ./rh.
#
# The dev command list lives in exactly one place (DEV_COMMANDS) and is rendered
# by both `./rh help` and `./rh dev help`. Previously the two screens each had
# their own hand-maintained copy and had already drifted apart.

# Gutter widths, matching the hand-aligned columns the help screens used before.
RH_PAD_CMD=23      # command tables
RH_PAD_WORKTREE=32 # the worktree table, whose commands are longer
RH_PAD_EXAMPLE=25  # the top-level Examples block

# Print one "  ./rh <command>   - <description>" row, padded so descriptions line
# up. Color codes have no printable width, so the padding is computed from the
# bare command and emitted outside the escapes.
help_row() {
    local command="$1"
    local description="$2"
    local pad=$((${3:-$RH_PAD_CMD} - ${#command}))
    [ "$pad" -lt 1 ] && pad=1
    printf "  ${GREEN}%s${NC}%*s- %s\n" "$command" "$pad" "" "$description"
}

# Same, but for the Examples blocks, which use "# comment" instead of "- text".
help_example() {
    local command="$1"
    local comment="$2"
    local pad=$((${3:-$RH_PAD_CMD} - ${#command}))
    [ "$pad" -lt 1 ] && pad=1
    printf "  ${BLUE}%s${NC}%*s# %s\n" "$command" "$pad" "" "$comment"
}

# ============================================================================
# Command tables — the single source of truth for the help output
# ============================================================================

# Each entry is "subcommand|description". Ports come from dev.sh so the help
# text cannot drift from the ports the containers actually bind.
rh_dev_setup_commands() {
    cat <<TABLE
init|Initialize env files (one-time setup)
up|Start dev infrastructure (postgres:${DEV_POSTGRES_PORT}, redis:${DEV_REDIS_PORT})
down|Stop dev infrastructure
clean|Remove containers and volumes (resets database)
status|Show dev environment status
TABLE
}

rh_dev_service_commands() {
    cat <<TABLE
backend|Start the backend server
seed|Seed local mock LLM + chatbot resources
frontend|Start the frontend server
worker|Start the Celery worker
mock-llm|Start the mock LLM server
mock-chatbot|Start the mock chatbot server
tmux|Start all dev services in a tmux session
chatbot|Start the chatbot server
docs|Start the documentation server
polyphemus|Start the Polyphemus service
TABLE
}

# Render a table produced by one of the functions above.
render_dev_table() {
    local line command description
    while IFS='|' read -r command description; do
        [ -n "$command" ] || continue
        help_row "./rh dev $command" "$description"
    done
}

# ============================================================================
# ./rh help
# ============================================================================

show_help() {
    echo -e "${CYAN}"
    echo "  ____  _   _ _____ ____ ___ ____  "
    echo " |  _ \| | | | ____/ ___|_ _/ ___| "
    echo " | |_) | |_| |  _| \___ \| |\___ \ "
    echo " |  _ <|  _  | |___ ___) | | ___) |"
    echo " |_| \_\_| |_|_____|____/___|____/ "
    echo -e "${NC}"
    echo ""
    echo -e "${WHITE}Rhesis CLI - Development Server Manager${NC}"
    echo -e "${PURPLE}════════════════════════════════════════${NC}"
    echo ""
    step "Usage:"
    help_row "./rh start" "Start all services (prebuilt GHCR images)"
    help_row "./rh start --build" "Start all services, building images locally"
    help_row "./rh stop" "Stop all Docker services"
    help_row "./rh restart" "Restart all Docker services"
    help_row "./rh restart --build" "Restart and rebuild images locally"
    help_row "./rh logs" "View logs from all services"
    help_row "./rh delete" "Delete all services, images, volumes, and data"
    help_row "./rh secrets" "Generate the required secrets in .env.docker"
    echo ""
    step "Local Development:"
    rh_dev_setup_commands | render_dev_table
    rh_dev_service_commands | render_dev_table
    echo ""
    step "Testing:"
    help_row "./rh test frontend" "Run frontend tests"
    echo ""
    step "Worktree:"
    help_row "./rh worktree <name>" "Create a worktree with shared env/config" "$RH_PAD_WORKTREE"
    help_row "./rh worktree <name> --remove" "Remove worktree and delete branch" "$RH_PAD_WORKTREE"
    help_row "./rh worktree <name> --load" "Launch shell in worktree" "$RH_PAD_WORKTREE"
    help_row "./rh worktree --list" "List all worktrees" "$RH_PAD_WORKTREE"
    echo ""
    step "Other:"
    help_row "./rh help" "Show this help message"
    echo ""
    step "Examples:"
    help_example "./rh start" "Start with prebuilt GHCR images" "$RH_PAD_EXAMPLE"
    help_example "./rh start --build" "Build and start from local Dockerfiles" "$RH_PAD_EXAMPLE"
    help_example "./rh dev init" "Initialize environment files (first time)" "$RH_PAD_EXAMPLE"
    help_example "./rh dev up" "Bring up dev infrastructure" "$RH_PAD_EXAMPLE"
    help_example "./rh dev backend" "Start backend locally (without Docker)" "$RH_PAD_EXAMPLE"
    help_example "./rh dev frontend" "Start frontend locally (without Docker)" "$RH_PAD_EXAMPLE"
    help_example "./rh stop" "Stop all Docker services" "$RH_PAD_EXAMPLE"
    help_example "./rh delete" "Delete everything (services, images, volumes, data)" "$RH_PAD_EXAMPLE"
    help_example "./rh logs backend" "View backend logs" "$RH_PAD_EXAMPLE"
    help_example "./rh test frontend" "Run frontend tests" "$RH_PAD_EXAMPLE"
    echo ""
}

# ============================================================================
# ./rh dev  /  ./rh dev help
# ============================================================================

show_dev_help() {
    head1 "Local Development Commands:"
    echo ""
    step "Setup:"
    rh_dev_setup_commands | render_dev_table
    echo ""
    step "Services:"
    rh_dev_service_commands | render_dev_table
    echo ""
    step "Typical workflow:"
    help_example "./rh dev init" "First time only"
    help_example "./rh dev up" "Each session"
    help_example "./rh dev backend" "In one terminal"
    help_example "./rh dev frontend" "In another terminal"
    echo ""
}

# ============================================================================
# ./rh test
# ============================================================================

show_test_help() {
    head1 "Testing Commands:"
    echo ""
    help_row "./rh test frontend" "Run frontend tests"
    echo ""
}
