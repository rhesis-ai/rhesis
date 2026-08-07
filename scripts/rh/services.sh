#!/bin/bash
# Service launchers for ./rh dev <service>, plus ./rh test.

CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
CELERY_WORKER_PREFETCH_MULTIPLIER="${CELERY_WORKER_PREFETCH_MULTIPLIER:-4}"

# Ports come from ports.sh, which ./rh sources ahead of this file.

# Mirrors apps/backend/Dockerfile build-backend. EE is included because deployed
# images ship it by default and gate it at runtime on the license.
BACKEND_UV_EXTRAS="--extra all --extra cpu --extra ee"

sync_backend_venv() {
    check_uv
    info "Syncing backend venv (uv sync ${BACKEND_UV_EXTRAS})..."
    # shellcheck disable=SC2086
    uv sync $BACKEND_UV_EXTRAS || die "Error: uv sync failed"
}

# ============================================================================
# Backend
# ============================================================================

start_backend() {
    echo -e "${GREEN}Starting Rhesis Backend...${NC}"
    cd_or_die "$SCRIPT_DIR/apps/backend" "Backend"

    sync_backend_venv

    # shellcheck disable=SC1091
    source .venv/bin/activate || die "Error: Failed to activate virtual environment"
    ok "Python environment activated"

    # Backgrounded because it polls /health itself; it exits after seeding or a
    # timeout, so the foreground server below is never blocked.
    ( seed_dev_resources ) &

    [ -f "start.sh" ] || die "Error: Backend start.sh not found"
    ./start.sh
}

# ============================================================================
# Frontend, docs, mocks — all just wrap a start.sh
# ============================================================================

start_frontend() {
    echo -e "${GREEN}Starting Rhesis Frontend...${NC}"
    # The npm script passes PORT to next dev as -p.
    export PORT="$DEV_FRONTEND_PORT"
    run_start_script apps/frontend "Frontend"
}

start_docs() {
    echo -e "${GREEN}Starting Rhesis Documentation...${NC}"
    run_start_script docs/src "Documentation"
}

start_mock_llm() {
    echo -e "${GREEN}Starting Mock LLM...${NC}"
    check_uv
    run_start_script apps/developer-tools "developer-tools" mock_llm/start.sh
}

start_mock_chatbot() {
    echo -e "${GREEN}Starting Mock Chatbot...${NC}"
    check_uv
    run_start_script apps/developer-tools "developer-tools" mock_chatbot/start.sh
}

# ============================================================================
# Chatbot
# ============================================================================

announce_uvicorn() {
    local port="$1"
    echo -e "${BLUE}Service will be available at: http://localhost:${port}${NC}"
    echo -e "${BLUE}API docs will be available at: http://localhost:${port}/docs${NC}"
    step "Press Ctrl+C to stop the service"
    echo ""
}

start_chatbot() {
    echo -e "${GREEN}Starting Rhesis Chatbot...${NC}"
    cd_or_die "$SCRIPT_DIR/apps/chatbot" "Chatbot"

    echo -e "${GREEN}Starting Chatbot service...${NC}"
    announce_uvicorn "$DEV_CHATBOT_PORT"

    exec uv run uvicorn client:app --host 0.0.0.0 --port "$DEV_CHATBOT_PORT" --reload
}

# ============================================================================
# Polyphemus
# ============================================================================

pip_install_editable() {
    local target="$1"
    local label="$2"
    step "Installing ${label}..."
    uv pip install -e "$target" || die "Error: Failed to install ${label}"
}

start_polyphemus() {
    echo -e "${GREEN}Starting Rhesis Polyphemus...${NC}"
    cd_or_die "$SCRIPT_DIR" "Script"

    if [ ! -d ".venv" ]; then
        step "Creating virtual environment..."
        uv venv || die "Error: Failed to create virtual environment"
    fi

    # shellcheck disable=SC1091
    source .venv/bin/activate || die "Error: Failed to activate virtual environment"

    # Order matters — polyphemus resolves only once these three are in place.
    step "Installing SDK with HuggingFace support..."
    uv pip install -e "sdk[huggingface]" || die "Error: Failed to install SDK"
    pip_install_editable penelope "Penelope"
    pip_install_editable apps/backend "Backend"
    pip_install_editable apps/polyphemus "Polyphemus"

    echo -e "${GREEN}Starting Polyphemus service...${NC}"
    announce_uvicorn "$DEV_POLYPHEMUS_PORT"

    exec uvicorn rhesis.polyphemus.main:app --host 0.0.0.0 --port "$DEV_POLYPHEMUS_PORT" --reload
}

# ============================================================================
# Celery worker + Flower
# ============================================================================

FLOWER_PID=""
WORKER_PID=""

# Scoped to this project — a bare "celery" would match another project's worker.
# Catches Flower too, which runs under the same -A. The leading "-A" is left off
# because pgrep/pkill would parse it as an option.
CELERY_APP_PATTERN='rhesis\.backend\.worker\.app'

# TERM first so in-flight tasks can finish; KILL only for stragglers.
stop_existing_celery() {
    step "Checking for existing Celery workers..."
    if ! pgrep -f "$CELERY_APP_PATTERN" > /dev/null; then
        info "No existing workers found"
        return 0
    fi

    step "Stopping existing Celery workers..."
    pkill -TERM -f "$CELERY_APP_PATTERN" 2>/dev/null || true

    local _
    for _ in {1..10}; do
        pgrep -f "$CELERY_APP_PATTERN" > /dev/null || break
        sleep 1
    done

    if pgrep -f "$CELERY_APP_PATTERN" > /dev/null; then
        warn "Workers did not stop gracefully — forcing"
        pkill -9 -f "$CELERY_APP_PATTERN" 2>/dev/null || true
        sleep 1
    fi

    ok "Existing workers stopped"
}

cleanup_worker_stack() {
    if [ -n "${WORKER_PID:-}" ] && kill -0 "$WORKER_PID" 2>/dev/null; then
        echo -e "\n${YELLOW}Stopping Celery worker (PID ${WORKER_PID})...${NC}"
        kill -TERM "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi
    if [ -n "${FLOWER_PID:-}" ] && kill -0 "$FLOWER_PID" 2>/dev/null; then
        step "Stopping Flower (PID ${FLOWER_PID})..."
        kill -TERM "$FLOWER_PID" 2>/dev/null || true
        wait "$FLOWER_PID" 2>/dev/null || true
    fi
}

start_worker() {
    echo -e "${GREEN}Starting Rhesis Worker...${NC}"

    stop_existing_celery

    step "Clearing Python cache..."
    cd_or_die "$SCRIPT_DIR" "Script"
    find apps/backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
    find apps/backend -type f -name "*.pyc" -delete 2>/dev/null
    ok "Cache cleared"

    cd_or_die "$SCRIPT_DIR/apps/backend" "Backend"
    sync_backend_venv

    local log_file="$SCRIPT_DIR/celery.log"
    echo -e "${GREEN}Starting new Celery worker...${NC}"
    echo -e "${BLUE}Logs will be written to: ${log_file}${NC}"
    step "Press Ctrl+C to stop the worker and Flower"
    echo ""

    # Run from the backend venv: apps/worker has no Python deps of its own, and
    # the Docker worker likewise reuses the backend image.
    export PYTHONPATH="${SCRIPT_DIR}/apps/backend/src${PYTHONPATH:+:$PYTHONPATH}"

    trap 'cleanup_worker_stack; exit 130' INT
    trap 'cleanup_worker_stack; exit 143' TERM

    echo -e "${GREEN}Starting Flower (Celery monitor)...${NC}"
    uv run celery -A rhesis.backend.worker.app flower --port="$DEV_FLOWER_PORT" &
    FLOWER_PID=$!
    echo -e "${BLUE}Flower dashboard: http://127.0.0.1:${DEV_FLOWER_PORT}/${NC}"
    echo -e "${BLUE}Override the port with: ${WHITE}DEV_FLOWER_PORT=<port> ./rh dev worker${NC}"
    echo ""

    # UUID suffix so rapid restarts cannot collide: worker@server1-a1b2c3d4
    local worker_uuid
    worker_uuid=$(python3 -c "import uuid; print(str(uuid.uuid4())[:8])")
    export CELERY_WORKER_NAME="worker@$(hostname)-${worker_uuid}"
    ok "CELERY_WORKER_NAME set to: ${CELERY_WORKER_NAME}"

    uv run celery -A rhesis.backend.worker.app worker \
        --pool threads \
        --loglevel=DEBUG \
        --queues=celery,execution,telemetry,architect \
        --concurrency="${CELERY_WORKER_CONCURRENCY}" \
        --prefetch-multiplier="${CELERY_WORKER_PREFETCH_MULTIPLIER}" \
        --optimization=fair \
        -E &
    WORKER_PID=$!

    wait "$WORKER_PID"
    local worker_rc=$?
    cleanup_worker_stack
    exit "$worker_rc"
}

# ============================================================================
# Tests
# ============================================================================

test_frontend() {
    echo -e "${GREEN}Running Frontend Tests...${NC}"
    cd_or_die "$SCRIPT_DIR/apps/frontend" "Frontend"

    if [ ! -d "node_modules" ]; then
        step "Installing dependencies first..."
        npm install || die "Error: Failed to install dependencies"
    fi

    info "Executing tests..."
    npm test || die "Error: Tests failed"

    ok "Frontend tests completed!"
}
