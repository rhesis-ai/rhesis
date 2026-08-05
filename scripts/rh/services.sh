#!/bin/bash
# Individual service launchers for ./rh dev <service> and ./rh test.
# These run in the foreground and generally end in exec or a blocking start.sh.

CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
CELERY_WORKER_PREFETCH_MULTIPLIER="${CELERY_WORKER_PREFETCH_MULTIPLIER:-4}"
FLOWER_PORT="${FLOWER_PORT:-5555}"

# The backend venv is shared by ./rh dev backend and ./rh dev worker, and matches
# apps/backend/Dockerfile build-backend: full optional deps + CPU PyTorch index +
# EE. The EE code ships in deployed images by default (license-based runtime
# gating), so dev parity means installing it here too.
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

    # Seed local dev resources once the backend is healthy. Runs in the background
    # (it waits for /health itself) so the foreground server below is not blocked;
    # it exits on its own after seeding or a timeout.
    ( seed_dev_resources ) &

    [ -f "start.sh" ] || die "Error: Backend start.sh not found"
    ./start.sh
}

# ============================================================================
# Frontend, docs, mocks — all just wrap a start.sh
# ============================================================================

start_frontend() {
    echo -e "${GREEN}Starting Rhesis Frontend...${NC}"
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

# Announce where a uvicorn-hosted service will be reachable.
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
    announce_uvicorn 8000

    exec uv run uvicorn client:app --host 0.0.0.0 --port 8000 --reload
}

# ============================================================================
# Polyphemus
# ============================================================================

# uv pip install -e <path>, dying with a labeled message on failure.
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

    # Order matters: polyphemus needs the SDK's huggingface extras, then Penelope,
    # then the backend, before its own dependencies resolve.
    step "Installing SDK with HuggingFace support..."
    uv pip install -e "sdk[huggingface]" || die "Error: Failed to install SDK"
    pip_install_editable penelope "Penelope"
    pip_install_editable apps/backend "Backend"
    pip_install_editable apps/polyphemus "Polyphemus"

    echo -e "${GREEN}Starting Polyphemus service...${NC}"
    announce_uvicorn 8082

    exec uvicorn rhesis.polyphemus.main:app --host 0.0.0.0 --port 8082 --reload
}

# ============================================================================
# Celery worker + Flower
# ============================================================================

FLOWER_PID=""
WORKER_PID=""

# Tear down both children on Ctrl+C, TERM, or a worker exit.
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

    step "Checking for existing Celery workers..."
    if pgrep -f celery > /dev/null; then
        step "Stopping existing Celery workers..."
        pkill -9 -f celery
        sleep 1
        ok "Existing workers stopped"
    else
        info "No existing workers found"
    fi

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

    # Flower is a backend dev dependency (default-groups includes dev).
    # apps/worker has no Python deps — the Docker worker reuses the backend image.
    export PYTHONPATH="${SCRIPT_DIR}/apps/backend/src${PYTHONPATH:+:$PYTHONPATH}"

    trap 'cleanup_worker_stack; exit 130' INT
    trap 'cleanup_worker_stack; exit 143' TERM

    echo -e "${GREEN}Starting Flower (Celery monitor)...${NC}"
    uv run celery -A rhesis.backend.worker.app flower --port="$FLOWER_PORT" &
    FLOWER_PID=$!
    echo -e "${BLUE}Flower dashboard: http://127.0.0.1:${FLOWER_PORT}/${NC}"
    echo -e "${BLUE}Override the port with: ${WHITE}FLOWER_PORT=<port> ./rh dev worker${NC}"
    echo ""

    # Unique worker name (hostname + short UUID) so rapid restarts never collide.
    # Format: worker@hostname-uuid, e.g. worker@server1-a1b2c3d4
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
