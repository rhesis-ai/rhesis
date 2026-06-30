#!/bin/bash

# Exit on any error
set -e

# ---------------------------------------------------------------------------
# Defaults — single source of truth for all tunables.
# Override any of these by setting the corresponding environment variable
# before starting the container.
# ---------------------------------------------------------------------------
: "${CELERY_WORKER_CONCURRENCY:=2}"            # threads for the main worker
: "${CELERY_ARCHITECT_CONCURRENCY:=2}"         # threads for the architect worker
: "${CELERY_WORKER_PREFETCH_MULTIPLIER:=4}"    # prefetch multiplier for the main worker
: "${CELERY_ARCHITECT_PREFETCH_MULTIPLIER:=4}" # prefetch multiplier for the architect worker
: "${CELERY_WORKER_LOGLEVEL:=WARNING}"         # overridden to DEBUG in dev below
: "${CELERY_WORKER_OPTS:=}"                   # extra flags passed to both workers
: "${ENABLE_FLOWER:=no}"
export CELERY_WORKER_CONCURRENCY CELERY_ARCHITECT_CONCURRENCY \
    CELERY_WORKER_PREFETCH_MULTIPLIER CELERY_ARCHITECT_PREFETCH_MULTIPLIER \
    CELERY_WORKER_LOGLEVEL CELERY_WORKER_OPTS ENABLE_FLOWER

# Print environment variables for debugging (excluding sensitive info)
echo "=== Environment Configuration Debug ==="
echo "BROKER_URL exists: $(if [ ! -z "$BROKER_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "CELERY_RESULT_BACKEND exists: $(if [ ! -z "$CELERY_RESULT_BACKEND" ]; then echo "yes"; else echo "no"; fi)"
echo "DB_HOST exists: $(if [ ! -z "$DB_HOST" ]; then echo "yes"; else echo "no"; fi)"
echo "Worker environment: ${WORKER_ENV:-not_set}"
echo "Git branch: ${GIT_BRANCH:-unknown}"
echo "Git commit: ${GIT_COMMIT:-unknown}"
echo "Celery worker concurrency: $CELERY_WORKER_CONCURRENCY"
echo "Celery architect concurrency: $CELERY_ARCHITECT_CONCURRENCY"
echo "Celery worker prefetch multiplier: $CELERY_WORKER_PREFETCH_MULTIPLIER"
echo "Celery architect prefetch multiplier: $CELERY_ARCHITECT_PREFETCH_MULTIPLIER"
echo "Celery worker pool: threads"

# Set log level based on worker environment
if [ "${WORKER_ENV}" = "development" ]; then
    CELERY_WORKER_LOGLEVEL="DEBUG"
    echo "🔧 Development environment detected - setting log level to DEBUG"
else
    echo "🔧 Production/staging environment - using log level: $CELERY_WORKER_LOGLEVEL"
fi

echo "Celery worker log level: $CELERY_WORKER_LOGLEVEL"

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

# Test Celery app import before starting worker
echo "Testing Celery app import..."
python -c "
import sys
try:
    from rhesis.backend.worker import app
    print('✅ Celery app imported successfully')
    print(f'Broker URL configured: {bool(app.conf.broker_url)}')
    print(f'Result backend configured: {bool(app.conf.result_backend)}')
except Exception as e:
    print(f'❌ Failed to import Celery app: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
"

# Test broker connectivity
echo "Testing broker connectivity..."
# Use longer timeout for TLS connections
if [[ "$BROKER_URL" == rediss://* ]]; then
    TIMEOUT=15
    echo "Detected TLS connection (rediss://), using longer timeout: ${TIMEOUT}s"
else
    TIMEOUT=10
    echo "Using standard timeout: ${TIMEOUT}s"
fi

timeout $TIMEOUT python -c "
import sys
import os
try:
    from rhesis.backend.worker import app
    print(f'Broker URL type: {\"TLS\" if os.getenv(\"BROKER_URL\", \"\").startswith(\"rediss://\") else \"standard\"}')
    
    # Test basic broker connection (lighter than worker ping)
    with app.connection() as conn:
        conn.connect()
        # Test basic broker communication
        conn.default_channel.basic_get('test_queue_connectivity_check', no_ack=True)
        print('✅ Broker connection and communication successful')
except Exception as e:
    print(f'⚠️ Broker connection warning: {e}')
    print('Note: This is expected during startup - workers will retry connections')
    # Don't exit here - let the worker handle retries
" || echo "⚠️ Broker connection test completed (timeouts are normal during startup)"

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

# Function to forward signals to children
forward_signal() {
    echo "Received shutdown signal, stopping processes..."
    
    if [ ! -z "$HEALTH_SERVER_PID" ] && kill -0 $HEALTH_SERVER_PID 2>/dev/null; then
        echo "Stopping health check server (PID: $HEALTH_SERVER_PID)..."
        kill -TERM $HEALTH_SERVER_PID || true
    fi
    
    if [ ! -z "$FLOWER_PID" ] && kill -0 $FLOWER_PID 2>/dev/null; then
        echo "Stopping Flower (PID: $FLOWER_PID)..."
        kill -TERM $FLOWER_PID || true
    fi
    
    if [ ! -z "$MAIN_PID" ] && kill -0 $MAIN_PID 2>/dev/null; then
        echo "Stopping main Celery worker (PID: $MAIN_PID)..."
        kill -TERM $MAIN_PID || true
        wait $MAIN_PID 2>/dev/null || true
    fi

    if [ ! -z "$ARCHITECT_PID" ] && kill -0 $ARCHITECT_PID 2>/dev/null; then
        echo "Stopping architect Celery worker (PID: $ARCHITECT_PID)..."
        kill -TERM $ARCHITECT_PID || true
        wait $ARCHITECT_PID 2>/dev/null || true
    fi
    
    exit 0
}

# Set up signal handling
trap forward_signal SIGTERM SIGINT

# Start Celery worker with configuration from environment variables
echo ""
echo "=== Celery Worker Startup ==="
echo "Starting Celery worker with full output..."

# Two workers share the same hostname; -n gives each a unique node name so
# they don't collide on the broker. %h expands to the container hostname.
# CELERY_WORKER_CONCURRENCY           -> main worker  (celery, execution, telemetry)
# CELERY_ARCHITECT_CONCURRENCY        -> architect worker (architect queue only)
# CELERY_WORKER_PREFETCH_MULTIPLIER   -> prefetch for main worker
# CELERY_ARCHITECT_PREFETCH_MULTIPLIER -> prefetch for architect worker
#
# Uses the threads pool: no fork(), so no fork-safety issues with native
# libraries (SSL, gRPC, Kerberos/CoreFoundation). Works well for I/O-bound
# work (LLM API calls, DB queries). -E enables events for Flower/monitoring.

MAIN_CMD="celery -A rhesis.backend.worker.app worker --pool threads -n main@%h --queues=celery,execution,telemetry --loglevel=$CELERY_WORKER_LOGLEVEL --concurrency=$CELERY_WORKER_CONCURRENCY --prefetch-multiplier=$CELERY_WORKER_PREFETCH_MULTIPLIER --optimization=fair -E $CELERY_WORKER_OPTS"
ARCHITECT_CMD="celery -A rhesis.backend.worker.app worker --pool threads -n architect@%h --queues=architect --loglevel=$CELERY_WORKER_LOGLEVEL --concurrency=$CELERY_ARCHITECT_CONCURRENCY --prefetch-multiplier=$CELERY_ARCHITECT_PREFETCH_MULTIPLIER --optimization=fair -E $CELERY_WORKER_OPTS"

echo "--- Main worker ---"
echo "Command:     $MAIN_CMD"
echo "Queues:      celery,execution,telemetry"
echo "Concurrency: $CELERY_WORKER_CONCURRENCY"
echo "Prefetch:    $CELERY_WORKER_PREFETCH_MULTIPLIER"
echo ""
echo "--- Architect worker ---"
echo "Command:     $ARCHITECT_CMD"
echo "Queues:      architect"
echo "Concurrency: $CELERY_ARCHITECT_CONCURRENCY"
echo "Prefetch:    $CELERY_ARCHITECT_PREFETCH_MULTIPLIER"
echo ""
echo "Pool:        threads"
echo "Log level:   $CELERY_WORKER_LOGLEVEL"
echo "Extra opts:  ${CELERY_WORKER_OPTS:-none}"

# Start main worker in background
$MAIN_CMD &
MAIN_PID=$!
echo "Main Celery worker started with PID: $MAIN_PID"

# Start architect worker in background
$ARCHITECT_CMD &
ARCHITECT_PID=$!
echo "Architect Celery worker started with PID: $ARCHITECT_PID"

# Enhanced startup monitoring — check both workers
echo ""
echo "=== Celery Worker Startup Monitoring ==="
for i in {1..10}; do
    MAIN_ALIVE=true
    ARCHITECT_ALIVE=true

    if ! kill -0 $MAIN_PID 2>/dev/null; then
        MAIN_ALIVE=false
    fi
    if ! kill -0 $ARCHITECT_PID 2>/dev/null; then
        ARCHITECT_ALIVE=false
    fi

    if [ "$MAIN_ALIVE" = "false" ] || [ "$ARCHITECT_ALIVE" = "false" ]; then
        if [ "$MAIN_ALIVE" = "false" ]; then
            echo "❌ Main Celery worker died after ${i} seconds!"
            wait $MAIN_PID 2>/dev/null; EXIT_CODE=$?
        else
            echo "❌ Architect Celery worker died after ${i} seconds!"
            wait $ARCHITECT_PID 2>/dev/null; EXIT_CODE=$?
        fi

        echo "Worker exit code: $EXIT_CODE"
        echo ""
        echo "=== Failure Analysis ==="
        echo "Checking system resources..."
        free -h 2>/dev/null || echo "Memory info not available"
        df -h 2>/dev/null || echo "Disk info not available"
        echo "Checking for core dumps..."
        ls -la core* 2>/dev/null || echo "No core dumps found"

        # Terminate the survivor before exiting
        kill -TERM $MAIN_PID 2>/dev/null || true
        kill -TERM $ARCHITECT_PID 2>/dev/null || true
        wait $MAIN_PID 2>/dev/null || true
        wait $ARCHITECT_PID 2>/dev/null || true

        exit $EXIT_CODE
    fi

    echo "Workers running... check $i/10 (main PID: $MAIN_PID, architect PID: $ARCHITECT_PID)"
    sleep 1
done

echo "✅ Both Celery workers are stable after 10 seconds"

# Test worker connectivity - wait for worker to be ready first
echo ""
echo "=== Worker Connectivity Test ==="
echo "Waiting for worker to fully initialize before connectivity test..."

# Give the worker time to fully start up
sleep 5

# Use same timeout logic as broker test  
if [[ "$BROKER_URL" == rediss://* ]]; then
    CONNECTIVITY_TIMEOUT=20
    echo "Using TLS timeout: ${CONNECTIVITY_TIMEOUT}s"
else
    CONNECTIVITY_TIMEOUT=15
    echo "Using standard timeout: ${CONNECTIVITY_TIMEOUT}s"
fi

# Try multiple times with increasing delays
for attempt in {1..3}; do
    echo "Connectivity test attempt $attempt/3..."
    
    timeout $CONNECTIVITY_TIMEOUT python -c "
import sys
import time
try:
    from rhesis.backend.worker import app
    
    # Give a moment for workers to register
    time.sleep(2)
    
    # Both workers (main@ and architect@) should respond
    result = app.control.inspect().ping()
    if result:
        print('✅ Workers are responding to ping')
        print(f'Active workers: {list(result.keys())}')
        print(f'Worker count: {len(result)}')
        sys.exit(0)
    else:
        print('⚠️ No workers responded to ping (this may be normal during startup)')
        sys.exit(1)
except Exception as e:
    print(f'❌ Worker connectivity test failed: {e}')
    sys.exit(1)
" && {
    echo "✅ Worker connectivity confirmed!"
    break
} || {
    if [ $attempt -eq 3 ]; then
        echo "⚠️ Worker connectivity test failed after 3 attempts"
        echo "Note: Workers may still be initializing - this is often normal"
    else
        echo "Retrying in 3 seconds..."
        sleep 3
    fi
}
done

# Supervise both workers: if either exits unexpectedly, tear down the other
# and exit non-zero so the orchestrator (K8s/compose) restarts the pod.
supervise_workers() {
    while true; do
        MAIN_ALIVE=true
        ARCHITECT_ALIVE=true

        kill -0 $MAIN_PID 2>/dev/null || MAIN_ALIVE=false
        kill -0 $ARCHITECT_PID 2>/dev/null || ARCHITECT_ALIVE=false

        if [ "$MAIN_ALIVE" = "false" ]; then
            wait $MAIN_PID 2>/dev/null; EXIT_CODE=$?
            echo "❌ Main Celery worker exited with code: $EXIT_CODE — stopping architect worker and exiting"
            kill -TERM $ARCHITECT_PID 2>/dev/null || true
            wait $ARCHITECT_PID 2>/dev/null || true
            return $EXIT_CODE
        fi

        if [ "$ARCHITECT_ALIVE" = "false" ]; then
            wait $ARCHITECT_PID 2>/dev/null; EXIT_CODE=$?
            echo "❌ Architect Celery worker exited with code: $EXIT_CODE — stopping main worker and exiting"
            kill -TERM $MAIN_PID 2>/dev/null || true
            wait $MAIN_PID 2>/dev/null || true
            return $EXIT_CODE
        fi

        sleep 5
    done
}

supervise_workers
EXIT_CODE=$?

# Clean up remaining processes
if [ ! -z "$HEALTH_SERVER_PID" ] && kill -0 $HEALTH_SERVER_PID 2>/dev/null; then
    echo "Stopping health check server..."
    kill -TERM $HEALTH_SERVER_PID || true
    wait $HEALTH_SERVER_PID 2>/dev/null || true
fi

if [ ! -z "$FLOWER_PID" ] && kill -0 $FLOWER_PID 2>/dev/null; then
    echo "Stopping Flower monitoring..."
    kill -TERM $FLOWER_PID || true
    wait $FLOWER_PID 2>/dev/null || true
fi

exit $EXIT_CODE 