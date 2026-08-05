#!/bin/bash
# Help screens for ./rh. The dev command list is defined once below and rendered
# by both ./rh help and ./rh dev help, which used to keep separate copies.

# Gutter widths, matching the columns these screens were hand-aligned to.
RH_PAD_CMD=23      # command tables
RH_PAD_WORKTREE=32 # the worktree table, whose commands are longer
RH_PAD_EXAMPLE=25  # the top-level Examples block

# Padding is computed from the bare command and emitted outside the color
# escapes, which have no printable width.
help_row() {
    local command="$1"
    local description="$2"
    local pad=$((${3:-$RH_PAD_CMD} - ${#command}))
    [ "$pad" -lt 1 ] && pad=1
    printf "  ${GREEN}%s${NC}%*s- %s\n" "$command" "$pad" "" "$description"
}

# For the Examples blocks, which use "# comment" instead of "- text".
help_example() {
    local command="$1"
    local comment="$2"
    local pad=$((${3:-$RH_PAD_CMD} - ${#command}))
    [ "$pad" -lt 1 ] && pad=1
    printf "  ${BLUE}%s${NC}%*s# %s\n" "$command" "$pad" "" "$comment"
}

# ============================================================================
# Command tables
# ============================================================================

# "subcommand|description". Ports come from dev.sh so the text cannot drift
# from what the containers actually bind.
rh_dev_setup_commands() {
    cat <<TABLE
init|Initialize env files (one-time setup)
up|Start dev infrastructure (postgres:${DEV_POSTGRES_PORT}, redis:${DEV_REDIS_PORT})
down|Stop dev infrastructure (database is kept)
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
    help_row "./rh worktree <name>" "Create a worktree with its own dev ports" "$RH_PAD_WORKTREE"
    help_row "./rh worktree <name> --remove" "Remove worktree, its containers, and branch" "$RH_PAD_WORKTREE"
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
    if [ -n "$RHESIS_WORKTREE_NAME" ]; then
        info "Worktree ${RHESIS_WORKTREE_NAME} — ports offset by ${RHESIS_PORT_OFFSET}"
    fi
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
