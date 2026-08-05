#!/bin/bash
# ./rh start | stop | restart | logs | delete | secrets — the Docker Compose
# "quickstart" stack that runs the whole platform in containers.

# ============================================================================
# Configuration
# ============================================================================

# A dedicated Compose project name keeps ./rh delete from touching containers
# that were created outside this script.
PROJECT_NAME="rhesis-quickstart"

# Written by ./rh start / ./rh restart so stop/logs/restart/delete reuse the same
# compose merge (GHCR images vs. local builds).
QUICKSTART_COMPOSE_MODE_FILE="$SCRIPT_DIR/.rhesis-quickstart-compose.mode"

QUICKSTART_ENV_FILE=".env.docker.local"

# ============================================================================
# Compose mode
# ============================================================================

# Returns ghcr or build (validated).
quickstart_compose_mode_from_file() {
    local mode="ghcr"
    if [ -f "$QUICKSTART_COMPOSE_MODE_FILE" ]; then
        mode=$(tr -d '[:space:]' < "$QUICKSTART_COMPOSE_MODE_FILE")
    fi
    if [ "$mode" = "build" ]; then
        echo "build"
    else
        echo "ghcr"
    fi
}

# Echoes docker compose -f ... flags for the given mode (ghcr = base + GHCR override).
quickstart_compose_flags_for_mode() {
    local mode="$1"
    if [ "$mode" = "build" ]; then
        echo "-f docker-compose.yml"
    else
        echo "-f docker-compose.yml -f docker-compose.ghcr.yml"
    fi
}

quickstart_compose_flags_from_file() {
    quickstart_compose_flags_for_mode "$(quickstart_compose_mode_from_file)"
}

# Every compose call in this file goes through here. COMPOSE_FLAGS is set by
# start_all/restart_all, which know the mode before it is written to disk;
# everything else falls back to the mode recorded by the last successful start.
# Unquoted on purpose — the flags are several words.
qs_compose() {
    # shellcheck disable=SC2086
    docker compose ${COMPOSE_FLAGS:-$(quickstart_compose_flags_from_file)} \
        -p "$PROJECT_NAME" --env-file "$QUICKSTART_ENV_FILE" "$@"
}

# The five services the quickstart stack brings up, in dependency order.
QUICKSTART_SERVICES="postgres redis backend worker frontend"
# Only these three are built locally; postgres and redis are always pulled.
QUICKSTART_BUILD_SERVICES="backend worker frontend"

# Build images from local Dockerfiles.
#
# Build and up are two separate calls rather than `up --build`: run together,
# Compose can deadlock — after the BuildKit build finishes it keeps waiting on the
# build result stream and never moves on to creating containers (the process sits
# idle with no Docker activity). BUILDX_NO_DEFAULT_ATTESTATIONS disables the
# provenance/attestation manifests whose export is what triggers the wedge.
qs_build() {
    # Subshell so the export does not outlive the build.
    (
        export BUILDX_NO_DEFAULT_ATTESTATIONS=1
        # shellcheck disable=SC2086
        qs_compose build $QUICKSTART_BUILD_SERVICES
    )
}

# ============================================================================
# ./rh secrets — fill an existing .env.docker (production flow)
# ============================================================================

# DB_ENCRYPTION_KEY is guarded: rotating it makes data already encrypted with the
# old key undecryptable, so it is overwritten only on explicit confirmation
# (default no). The other three are safe to rotate and are set unconditionally.
generate_docker_secrets() {
    if [ ! -f ".env.docker" ]; then
        err ".env.docker not found"
        echo -e "${YELLOW}   Create it first: ${GREEN}cp .env.example .env.docker${NC}"
        exit 1
    fi

    if grep -qE "^DB_ENCRYPTION_KEY=[^[:space:]]" .env.docker 2>/dev/null; then
        warn "DB_ENCRYPTION_KEY is already set in .env.docker."
        echo -e "${WHITE}   Overwriting it makes data already encrypted with the old key"
        echo -e "   (such as stored provider credentials) permanently undecryptable.${NC}"
        if confirm "Overwrite DB_ENCRYPTION_KEY?"; then
            set_env_var .env.docker "DB_ENCRYPTION_KEY" "$(generate_encryption_key)"
            ok "DB_ENCRYPTION_KEY regenerated"
        else
            note "   Kept existing DB_ENCRYPTION_KEY."
        fi
    else
        set_env_var .env.docker "DB_ENCRYPTION_KEY" "$(generate_encryption_key)"
        ok "DB_ENCRYPTION_KEY generated"
    fi

    set_env_var .env.docker "JWT_SECRET_KEY" "$(generate_hex_secret)"
    set_env_var .env.docker "SESSION_SECRET_KEY" "$(generate_hex_secret)"
    set_env_var .env.docker "NEXTAUTH_SECRET" "$(generate_hex_secret)"
    ok "JWT_SECRET_KEY, SESSION_SECRET_KEY, NEXTAUTH_SECRET set"

    chmod 600 .env.docker
    ok "Secrets written to .env.docker"
}

# ============================================================================
# .env.docker.local — the quickstart's generated config
# ============================================================================

# Create .env.docker.local from scratch, asking which host ports to bind.
quickstart_create_env_file() {
    local encryption_key="$1"

    echo ""
    step "🔌 Host ports"
    note "   Choose the host ports for Rhesis (press Enter to accept the default)."
    echo ""
    local backend_port frontend_port
    backend_port=$(prompt_port "backend" 8080)
    frontend_port=$(prompt_port "frontend" 3000)
    ok "Using backend port ${backend_port}, frontend port ${frontend_port}"

    # Compose keeps the bind ports and the public URLs decoupled, but for
    # localhost dev the public URL is just localhost on the chosen port, so
    # derive and write both here.
    cat > "$QUICKSTART_ENV_FILE" << EOF
# Auto-generated local environment configuration

# Database Encryption
DB_ENCRYPTION_KEY=${encryption_key}

# Local Authentication Bypass
QUICK_START=true

# Host ports and matching public URLs
BACKEND_PORT=${backend_port}
FRONTEND_PORT=${frontend_port}
API_BASE_URL=http://localhost:${backend_port}
FRONTEND_URL=http://localhost:${frontend_port}
EOF
    ok "Created ${QUICKSTART_ENV_FILE} with local configuration"
}

# Ensure DB_ENCRYPTION_KEY and QUICK_START are present in an existing file.
quickstart_update_env_file() {
    local encryption_key="$1"
    set_env_var "$QUICKSTART_ENV_FILE" "DB_ENCRYPTION_KEY" "$encryption_key"
    if ! grep -q "^QUICK_START=" "$QUICKSTART_ENV_FILE" 2>/dev/null; then
        echo "QUICK_START=true" >> "$QUICKSTART_ENV_FILE"
    fi
    ok "Local configuration updated in ${QUICKSTART_ENV_FILE}"
}

# Offer to store a Rhesis API key, which test generation needs.
quickstart_prompt_api_key() {
    grep -q "^RHESIS_API_KEY=" "$QUICKSTART_ENV_FILE" 2>/dev/null && return 0

    local api_key=""
    echo ""
    step "🔑 Rhesis API Key"
    note "   Test generation requires a Rhesis API key to call the generation service."
    echo -e "${WHITE}   Get your key at: ${CYAN}https://app.rhesis.ai/tokens${NC}"
    echo ""

    if [ -t 0 ]; then
        read -r -p "$(echo -e "${YELLOW}Enter your RHESIS_API_KEY (or press Enter to skip): ${NC}")" api_key
        echo
    fi

    if [ -z "$api_key" ]; then
        warn "Skipping — test generation will not work without a valid API key"
        echo -e "${YELLOW}   Add it later: ${WHITE}RHESIS_API_KEY=<your-key>${YELLOW} in ${QUICKSTART_ENV_FILE}${NC}"
        return 0
    fi

    {
        echo ""
        echo "# Rhesis API Key (required for test generation)"
        echo "RHESIS_API_KEY=$api_key"
    } >> "$QUICKSTART_ENV_FILE"
    chmod 600 "$QUICKSTART_ENV_FILE"
    ok "RHESIS_API_KEY saved to ${QUICKSTART_ENV_FILE}"
}

# Bring .env.docker.local up to the state `docker compose up` expects.
quickstart_prepare_env_file() {
    if [ ! -f "$QUICKSTART_ENV_FILE" ] || \
       ! grep -qE "^DB_ENCRYPTION_KEY=[^[:space:]]" "$QUICKSTART_ENV_FILE" 2>/dev/null; then
        step "🔑 Generating DB_ENCRYPTION_KEY..."
        local encryption_key
        encryption_key=$(gen_secret generate_encryption_key "encryption key") || exit 1

        if [ ! -f "$QUICKSTART_ENV_FILE" ]; then
            quickstart_create_env_file "$encryption_key"
        else
            quickstart_update_env_file "$encryption_key"
        fi
    fi

    # Required by docker-compose.yml.
    ensure_env_secret "$QUICKSTART_ENV_FILE" "JWT_SECRET_KEY" generate_hex_secret
    ensure_env_secret "$QUICKSTART_ENV_FILE" "SESSION_SECRET_KEY" generate_hex_secret
    ensure_env_secret "$QUICKSTART_ENV_FILE" "NEXTAUTH_SECRET" generate_hex_secret
    chmod 600 "$QUICKSTART_ENV_FILE"

    quickstart_prompt_api_key
}

# ============================================================================
# ./rh start
# ============================================================================

# True when --build appears in the arguments.
wants_build() {
    local arg
    for arg in "$@"; do
        [ "$arg" = "--build" ] && return 0
    done
    return 1
}

start_all() {
    echo -e "${GREEN}Starting all Rhesis services with Docker...${NC}"
    info "Using zero-configuration local setup"
    echo ""
    echo "#####################################################################################"
    echo ""
    head1 "Telemetry Notice:"
    note "   Rhesis AI automatically collects anonymous usage statistics to help improve the platform."
    echo -e "${WHITE}   To disable telemetry, set: ${YELLOW}OTEL_RHESIS_TELEMETRY_ENABLED=false${NC}"
    echo ""
    echo "#####################################################################################"
    echo ""

    cd_or_die "$SCRIPT_DIR" "Script"
    check_docker

    local use_build=0
    wants_build "$@" && use_build=1

    local quickstart_mode="ghcr"
    [ "$use_build" -eq 1 ] && quickstart_mode="build"
    COMPOSE_FLAGS=$(quickstart_compose_flags_for_mode "$quickstart_mode")

    quickstart_prepare_env_file

    echo ""
    step "Starting services ..."

    local compose_rc=0
    if [ "$use_build" -eq 1 ]; then
        qs_build
        compose_rc=$?
    else
        # shellcheck disable=SC2086
        qs_compose pull $QUICKSTART_SERVICES
        compose_rc=$?
    fi

    if [ "$compose_rc" -eq 0 ]; then
        # shellcheck disable=SC2086
        qs_compose up -d $QUICKSTART_SERVICES
        compose_rc=$?
    fi

    if [ "$compose_rc" -ne 0 ]; then
        die "Error: Failed to start services"
    fi

    echo "$quickstart_mode" > "$QUICKSTART_COMPOSE_MODE_FILE"
    echo ""
    ok "All services started successfully!"
    echo ""
    local backend_port frontend_port
    backend_port=$(grep -m1 "^BACKEND_PORT=" "$QUICKSTART_ENV_FILE" 2>/dev/null | cut -d= -f2)
    frontend_port=$(grep -m1 "^FRONTEND_PORT=" "$QUICKSTART_ENV_FILE" 2>/dev/null | cut -d= -f2)
    head1 "Access the platform:"
    echo -e "   Frontend:  ${WHITE}http://localhost:${frontend_port:-3000}${NC} (auto-login enabled)"
    echo -e "   Backend:   ${WHITE}http://localhost:${backend_port:-8080}/docs${NC}"
    echo ""
    step "Useful commands:"
    echo -e "   View logs:    ${GREEN}./rh logs${NC}"
    echo -e "   Stop all:     ${GREEN}./rh stop${NC}"
    echo -e "   Restart all:  ${GREEN}./rh restart${NC}"
    echo ""
}

# ============================================================================
# ./rh stop / restart / logs
# ============================================================================

stop_all() {
    step "Stopping all Rhesis services..."

    cd_or_die "$SCRIPT_DIR" "Script"

    if qs_compose down; then
        ok "All services stopped"
    else
        die "Error: Failed to stop services"
    fi
}

# Recreates containers so .env.docker.local changes apply.
# Optional: --build  Rebuild from local Dockerfiles and switch quickstart mode to build.
restart_all() {
    step "Restarting all Rhesis services..."

    cd_or_die "$SCRIPT_DIR" "Script"
    check_docker

    local use_build=0
    wants_build "$@" && use_build=1

    local quickstart_mode
    if [ "$use_build" -eq 1 ]; then
        quickstart_mode="build"
    else
        quickstart_mode=$(quickstart_compose_mode_from_file)
    fi
    COMPOSE_FLAGS=$(quickstart_compose_flags_for_mode "$quickstart_mode")

    local compose_rc=0
    if [ "$use_build" -eq 1 ]; then
        qs_build
        compose_rc=$?
    fi

    if [ "$compose_rc" -eq 0 ]; then
        # shellcheck disable=SC2086
        qs_compose up -d --force-recreate $QUICKSTART_SERVICES
        compose_rc=$?
    fi

    if [ "$compose_rc" -ne 0 ]; then
        die "Error: Failed to restart services"
    fi

    echo "$quickstart_mode" > "$QUICKSTART_COMPOSE_MODE_FILE"
    ok "All services restarted with current ${QUICKSTART_ENV_FILE}"
}

view_logs() {
    info "Viewing logs..."

    cd_or_die "$SCRIPT_DIR" "Script"

    if [ -z "$1" ]; then
        qs_compose logs -f
    else
        qs_compose logs -f "$1"
    fi
}

# ============================================================================
# ./rh delete
# ============================================================================

delete_all() {
    echo -e "${RED}⚠️  WARNING: This will delete Docker resources created by ./rh start!${NC}"
    step "This includes:"
    echo -e "  - Containers managed by ./rh (project: ${PROJECT_NAME})"
    echo -e "  - Docker images built by this project"
    echo -e "  - Volumes created by this project (DATABASE DATA WILL BE LOST!)"
    echo -e "  - Networks created by this project"
    echo -e "  - ${QUICKSTART_ENV_FILE}"
    echo ""
    info "Note: Containers created manually will NOT be affected"
    echo ""
    echo -e "${RED}This action CANNOT be undone!${NC}"
    echo ""
    if ! confirm_typed "Are you sure you want to continue?"; then
        echo ""
        ok "Deletion cancelled"
        exit 0
    fi
    echo ""

    step "Deleting Docker resources for this project..."

    cd_or_die "$SCRIPT_DIR" "Script"

    # The explicit project name keeps this scoped to resources THIS script created,
    # rather than containers with similar names from other projects.
    local compose_rc=0
    qs_compose down -v --rmi all 2>/dev/null || {
        # Fallback: if the project name does not match, try without -p.
        warn "Project-specific deletion failed, trying default method..."
        # shellcheck disable=SC2086
        docker compose ${COMPOSE_FLAGS:-$(quickstart_compose_flags_from_file)} \
            --env-file "$QUICKSTART_ENV_FILE" down -v --rmi all
        compose_rc=$?
    }

    rm -f "$QUICKSTART_ENV_FILE"
    rm -f "$QUICKSTART_COMPOSE_MODE_FILE"

    if [ "$compose_rc" -ne 0 ]; then
        die "Error: Failed to delete all resources"
    fi

    echo ""
    ok "Docker resources deleted successfully!"
    echo ""
    head1 "To start fresh:"
    echo -e "   ${GREEN}./rh start${NC}"
    echo ""
}
