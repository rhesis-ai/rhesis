#!/bin/bash

# Exit on any error
set -e

# ---------------------------------------------------------------------------
# Defaults — single source of truth for all tunables.
# Override any of these by setting the corresponding environment variable
# before starting the container.
#
# WORKER_LAYOUT picks how the queues are spread over Celery processes:
#   combined  two processes, main (every queue but architect) and architect.
#             For one worker container (docker compose, ./rh start).
#   split     one process per execution class (celery/config.py QUEUES), each
#             sized for its work. For replicated deployments (the Helm chart).
# All processes share the container's CPU; an idle thread costs none.
# ---------------------------------------------------------------------------
: "${WORKER_LAYOUT:=combined}"
: "${CELERY_WORKER_CONCURRENCY:=2}"            # combined: threads for the main worker
: "${CELERY_ARCHITECT_CONCURRENCY:=2}"         # threads for the architect worker
# Prefetch above 1: with acks_late on Redis a worker fetches roughly one message per
# poll per prefetch slot, so at 1 short tasks leave most threads idle (measured: 24 %
# of slots busy at 1, 97 % at 8). Long jobs keep 1 so one replica cannot hoard runs.
: "${CELERY_WORKER_PREFETCH_MULTIPLIER:=4}"    # combined: main worker
: "${CELERY_ARCHITECT_PREFETCH_MULTIPLIER:=1}"
: "${CELERY_LONG_CONCURRENCY:=24}"             # split: test-runs, long-jobs
: "${CELERY_INGEST_CONCURRENCY:=16}"           # split: trace-ingest
: "${CELERY_FAST_CONCURRENCY:=32}"             # split: trace-eval, quick-tasks, maintenance
: "${CELERY_FAST_PREFETCH_MULTIPLIER:=8}"      # split: trace-ingest and the fast queues
: "${LOG_LEVEL:=INFO}"                         # application logs (set_logger() root logger)
: "${CELERY_WORKER_LOGLEVEL:=$LOG_LEVEL}"      # celery's own task-lifecycle logger; defaults to LOG_LEVEL
: "${CELERY_WORKER_OPTS:=}"                   # extra flags passed to every worker
: "${ENABLE_FLOWER:=no}"
export WORKER_LAYOUT CELERY_WORKER_CONCURRENCY CELERY_ARCHITECT_CONCURRENCY \
    CELERY_WORKER_PREFETCH_MULTIPLIER CELERY_ARCHITECT_PREFETCH_MULTIPLIER \
    LOG_LEVEL CELERY_WORKER_LOGLEVEL CELERY_WORKER_OPTS ENABLE_FLOWER

# Print environment variables for debugging (excluding sensitive info)
echo "=== Environment Configuration Debug ==="
echo "BROKER_URL exists: $(if [ ! -z "$BROKER_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "CELERY_RESULT_BACKEND exists: $(if [ ! -z "$CELERY_RESULT_BACKEND" ]; then echo "yes"; else echo "no"; fi)"
echo "DB_HOST exists: $(if [ ! -z "$DB_HOST" ]; then echo "yes"; else echo "no"; fi)"
echo "Worker environment: ${WORKER_ENV:-not_set}"
echo "Git branch: ${GIT_BRANCH:-unknown}"
echo "Git commit: ${GIT_COMMIT:-unknown}"
echo "Worker layout: $WORKER_LAYOUT (each worker's settings are printed when it starts)"

echo "🔧 Application log level: ${LOG_LEVEL}"
echo "🔧 Celery log level: ${CELERY_WORKER_LOGLEVEL}"

# Enhanced TLS detection and debugging
if [[ "$BROKER_URL" == rediss://* ]]; then
    echo "🔒 TLS DETECTED: Broker URL uses rediss:// (TLS/SSL)"
    echo "TLS Connection Type: Redis with SSL/TLS"
elif [[ "$BROKER_URL" == redis://* ]]; then
    echo "🔓 STANDARD: Broker URL uses redis:// (no TLS)"
    echo "Connection Type: Standard Redis"
else
    echo "⚠️ UNKNOWN: Broker URL format not recognized"
    echo "Broker URL prefix: $(echo "$BROKER_URL" | cut -d':' -f1)"
fi

# System and network debugging
echo ""
echo "=== System Debug Information ==="
echo "Container hostname: $(hostname)"
echo "Container IP: $(hostname -i 2>/dev/null || echo 'N/A')"
echo "Python version: $(python --version)"
echo "Current user: $(whoami)"
echo "Working directory: $(pwd)"
echo "Available memory: $(if command -v free >/dev/null 2>&1; then free -h | grep Mem | awk '{print $7}' 2>/dev/null || echo 'N/A'; else echo 'N/A (free command not available)'; fi)"
echo "CPU cores: $(nproc 2>/dev/null || echo 'N/A')"

# Test Python environment
echo ""
echo "=== Python Environment Debug ==="
python -c "
import sys
import os
print(f'Python executable: {sys.executable}')
print(f'Python path entries: {len(sys.path)}')
print(f'PYTHONPATH: {os.getenv(\"PYTHONPATH\", \"Not set\")}')
try:
    import redis
    print(f'Redis module version: {redis.__version__ if hasattr(redis, \"__version__\") else \"available\"}')
except ImportError:
    print('❌ Redis module not available')
try:
    import celery
    print(f'Celery module version: {celery.__version__ if hasattr(celery, \"__version__\") else \"available\"}')
except ImportError:
    print('❌ Celery module not available')
"


# Broker reachability, with redis-py alone: importing the app here would cost the
# pod a full backend import at boot, on the same CPU the workers start on.
echo "Testing broker connectivity..."
timeout 15 python -c "
import os, redis
try:
    redis.Redis.from_url(os.environ['BROKER_URL'], socket_connect_timeout=10).ping()
    print('✅ Broker reachable')
except Exception as e:
    print(f'⚠️ Broker not reachable yet: {e} (workers retry on their own)')
" || echo "⚠️ Broker check timed out (workers retry on their own)"

# Start the health check server
echo "Starting health check server on port 8080..."
python /app/health_server.py &
HEALTH_SERVER_PID=$!
echo "Health server started with PID: $HEALTH_SERVER_PID"

# Wait a moment and verify health server is responding
echo ""
echo "=== Health Server Startup Verification ==="
echo "Health server PID: $HEALTH_SERVER_PID"
echo "Waiting for health server to be ready..."

for i in {1..10}; do
    # Check if process is still running first
    if ! kill -0 $HEALTH_SERVER_PID 2>/dev/null; then
        echo "❌ Health server process died (PID: $HEALTH_SERVER_PID)"
        echo "Checking process status..."
        ps aux | grep health_server.py | grep -v grep || echo "No health server processes found"
        break
    fi

    # Test basic endpoint
    if curl -f -s http://localhost:8080/health/basic > /dev/null 2>&1; then
        echo "✅ Health server is responding to /health/basic"

        # Also test the ping endpoint
        if curl -f -s http://localhost:8080/ping > /dev/null 2>&1; then
            echo "✅ Health server is responding to /ping"
        else
            echo "⚠️ Health server not responding to /ping"
        fi

        # Test debug endpoint availability
        if curl -f -s http://localhost:8080/debug > /dev/null 2>&1; then
            echo "✅ Debug endpoints are available"
        else
            echo "⚠️ Debug endpoints not available"
        fi
        break
    fi

    echo "Waiting for health server... attempt $i/10"
    sleep 1
done

# Verify all endpoints after startup
echo ""
echo "=== Health Server Endpoint Verification ==="
echo "Available endpoints:"
for endpoint in "ping" "health/basic" "health" "debug" "debug/env" "debug/redis"; do
    if curl -f -s "http://localhost:8080/$endpoint" > /dev/null 2>&1; then
        echo "  ✅ /$endpoint - responding"
    else
        echo "  ❌ /$endpoint - not responding"
    fi
done

# Start Flower monitoring tool if ENABLE_FLOWER is set
if [ "$ENABLE_FLOWER" = "yes" ]; then
    echo "Starting Flower monitoring on port 5555..."
    celery -A rhesis.backend.worker.app flower --port=5555 &
    FLOWER_PID=$!
    echo "Flower started with PID: $FLOWER_PID"
fi

# ---------------------------------------------------------------------------
# Celery workers
# ---------------------------------------------------------------------------
# Threads pool everywhere but the CPU class: no fork(), so no fork-safety issues with
# native libraries (SSL, gRPC), and the work is I/O. No -E: celery/config.py turns task
# events off; add it via CELERY_WORKER_OPTS when Flower needs a live task view.
#
# Each entry: node|queues|pool|concurrency|prefetch|db_pool|db_overflow|nice
# db_pool/db_overflow size the process's SQLAlchemy pool (DB_POOL_SIZE/DB_MAX_OVERFLOW);
# tasks hold a connection only for their queries, so the pool is smaller than the
# thread count. nice lowers a process's CPU priority under contention.
#
# The previous release's queue names (celery, execution, telemetry) are consumed too,
# so messages it queued still drain after an upgrade.
if [ "$WORKER_LAYOUT" = "split" ]; then
    WORKERS=(
        "long|test-runs,long-jobs,execution|threads|$CELERY_LONG_CONCURRENCY|1|10|14|0"
        "ingest|trace-ingest|threads|$CELERY_INGEST_CONCURRENCY|$CELERY_FAST_PREFETCH_MULTIPLIER|8|8|0"
        "fast|trace-eval,quick-tasks,maintenance,celery,telemetry|threads|$CELERY_FAST_CONCURRENCY|$CELERY_FAST_PREFETCH_MULTIPLIER|10|14|5"
        "architect|architect|threads|$CELERY_ARCHITECT_CONCURRENCY|$CELERY_ARCHITECT_PREFETCH_MULTIPLIER|4|6|0"
        "cpu|cpu-bound|prefork|1|1|2|2|10"
    )
else
    # Every queue in celery/config.py QUEUES but architect.
    MAIN_QUEUES="test-runs,long-jobs,trace-ingest,trace-eval,quick-tasks,cpu-bound,maintenance,celery,execution,telemetry"
    WORKERS=(
        "main|$MAIN_QUEUES|threads|$CELERY_WORKER_CONCURRENCY|$CELERY_WORKER_PREFETCH_MULTIPLIER|10|20|0"
        "architect|architect|threads|$CELERY_ARCHITECT_CONCURRENCY|$CELERY_ARCHITECT_PREFETCH_MULTIPLIER|4|6|0"
    )
fi

echo ""
echo "=== Celery Worker Startup ($WORKER_LAYOUT) ==="
WORKER_PIDS=()
WORKER_NAMES=()
for spec in "${WORKERS[@]}"; do
    IFS='|' read -r node queues pool concurrency prefetch db_pool db_overflow niceness <<< "$spec"
    # -n gives each process its own node name; %h expands to the container hostname.
    cmd="celery -A rhesis.backend.worker.app worker --pool $pool -n $node@%h --queues=$queues --loglevel=$CELERY_WORKER_LOGLEVEL --concurrency=$concurrency --prefetch-multiplier=$prefetch --optimization=fair $CELERY_WORKER_OPTS"
    # A forked child is recycled so a leak in native code cannot grow without bound.
    [ "$pool" = "prefork" ] && cmd="$cmd --max-tasks-per-child=20"
    echo "--- $node: $cmd (db pool $db_pool+$db_overflow, nice $niceness)"
    # RHESIS_PROCESS_ROLE becomes the Postgres application_name (database.py), so
    # pg_stat_activity can tell the processes and the API apart.
    RHESIS_PROCESS_ROLE="rhesis-celery-$node" DB_POOL_SIZE="$db_pool" DB_MAX_OVERFLOW="$db_overflow" \
        nice -n "$niceness" $cmd &
    WORKER_PIDS+=($!)
    WORKER_NAMES+=("$node")
    echo "$node worker started with PID: $!"
done

# Forward a shutdown to every child and wait for the workers' warm shutdown.
forward_signal() {
    echo "Received shutdown signal, stopping processes..."
    for pid in $HEALTH_SERVER_PID $FLOWER_PID; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in "${WORKER_PIDS[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    for pid in "${WORKER_PIDS[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
    exit 0
}
trap forward_signal SIGTERM SIGINT

# Supervise: if any worker exits, stop the rest and exit non-zero so the orchestrator
# (K8s/compose) restarts the pod. The pod's health checks cover readiness.
set +e
while true; do
    for i in "${!WORKER_PIDS[@]}"; do
        if ! kill -0 "${WORKER_PIDS[$i]}" 2>/dev/null; then
            wait "${WORKER_PIDS[$i]}"; EXIT_CODE=$?
            echo "❌ ${WORKER_NAMES[$i]} worker exited with code: $EXIT_CODE — stopping the others"
            for pid in "${WORKER_PIDS[@]}" $HEALTH_SERVER_PID $FLOWER_PID; do
                kill -TERM "$pid" 2>/dev/null || true
            done
            for pid in "${WORKER_PIDS[@]}"; do
                wait "$pid" 2>/dev/null || true
            done
            exit "${EXIT_CODE:-1}"
        fi
    done
    sleep 5
done
