#!/bin/bash

# Exit on any error
set -e

# Print environment variables for debugging (excluding sensitive info)
echo "=== Environment Configuration Debug ==="
echo "BROKER_URL exists: $(if [ ! -z "$BROKER_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "CELERY_RESULT_BACKEND exists: $(if [ ! -z "$CELERY_RESULT_BACKEND" ]; then echo "yes"; else echo "no"; fi)"
echo "SQLALCHEMY_DATABASE_URL exists: $(if [ ! -z "$SQLALCHEMY_DATABASE_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "Worker environment: ${WORKER_ENV:-not_set}"
echo "Celery worker concurrency: ${CELERY_WORKER_CONCURRENCY:-2}"
echo "Celery worker max tasks per child: ${CELERY_WORKER_MAX_TASKS_PER_CHILD:-500}"

# Set log level based on worker environment
if [ "${WORKER_ENV}" = "development" ]; then
    export CELERY_WORKER_LOGLEVEL="DEBUG"
    echo "🔧 Development environment detected - setting log level to DEBUG"
else
    export CELERY_WORKER_LOGLEVEL="${CELERY_WORKER_LOGLEVEL:-WARNING}"
    echo "🔧 Production/staging environment - using log level: ${CELERY_WORKER_LOGLEVEL}"
fi

echo "Celery worker log level: ${CELERY_WORKER_LOGLEVEL}"

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

# Override database URL for TCP connection if needed
if [ "${USE_TCP_DATABASE:-false}" = "true" ]; then
    echo "🔧 Overriding database URL for TCP connection..."
    echo "Original SQLALCHEMY_DATABASE_URL: ${SQLALCHEMY_DATABASE_URL}"
    
    # Construct TCP database URL from components
    export SQLALCHEMY_DATABASE_URL="postgresql://${SQLALCHEMY_DB_USER:-}:${SQLALCHEMY_DB_PASS:-}@${SQLALCHEMY_DB_HOST:-127.0.0.1}:${SQLALCHEMY_DB_PORT:-5432}/${SQLALCHEMY_DB_NAME:-}"
    echo "TCP SQLALCHEMY_DATABASE_URL: ${SQLALCHEMY_DATABASE_URL}"
    
    # Also set individual components for consistency
    echo "Database host: ${SQLALCHEMY_DB_HOST}"
    echo "Database port: ${SQLALCHEMY_DB_PORT}"
    echo "Database name: ${SQLALCHEMY_DB_NAME}"
    echo "Database user: ${SQLALCHEMY_DB_USER}"
fi

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

# Test database connectivity if TCP mode is enabled
if [ "${USE_TCP_DATABASE:-false}" = "true" ]; then
    echo "Testing database connectivity (TCP mode)..."
    timeout 10 python -c "
import sys
try:
    from sqlalchemy import create_engine, text
    import os
    
    # Test database connection
    db_url = os.getenv('SQLALCHEMY_DATABASE_URL')
    print(f'Testing database connection: {db_url.replace(os.getenv(\"SQLALCHEMY_DB_PASS\", \"\"), \"***\")}')
    
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)
" || echo "⚠️ Database connection test timed out or failed"
fi

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
if [ "${ENABLE_FLOWER:-no}" = "yes" ]; then
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
    
    if [ ! -z "$CELERY_PID" ] && kill -0 $CELERY_PID 2>/dev/null; then
        echo "Stopping Celery worker (PID: $CELERY_PID)..."
        kill -TERM $CELERY_PID || true
        wait $CELERY_PID
    fi
    
    exit 0
}

# Set up signal handling
trap forward_signal SIGTERM SIGINT

# Start Celery worker with configuration from environment variables
echo ""
echo "=== Celery Worker Startup ==="
echo "Starting Celery worker with full output..."

# Set worker context environment variable for RPC detection
# Using hostname-PID combination to ensure uniqueness across all workers
export CELERY_WORKER_NAME="worker@$(hostname)-$$"
echo "Worker context identifier: $CELERY_WORKER_NAME"

# Build the complete command with memory optimizations
# NOTE: Using --pool=solo instead of prefork to avoid process-level race conditions
# during test execution. With prefork, multiple worker processes can interfere with
# each other when writing test results simultaneously, causing:
# - Test metadata to get mixed up (e.g., robustness tests showing as reliability tests)
# - Intermittent database race conditions
# - Inconsistent test result data
# 
# Solo pool processes one task at a time per worker, eliminating these issues.
# To maintain throughput, scale horizontally by running more worker containers.
# See: https://github.com/rhesis-ai/rhesis/pull/728
# -E enables events for worker discovery by backend enrichment service
CELERY_CMD="celery -A rhesis.backend.worker.app worker --queues=celery,execution,telemetry --loglevel=${CELERY_WORKER_LOGLEVEL:-WARNING} --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-1} --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-500} --pool=solo --optimization=fair -E ${CELERY_WORKER_OPTS}"

echo "Command: $CELERY_CMD"
echo "Queues: celery,execution,telemetry"
echo "Pool: solo (sequential processing to avoid race conditions)"
echo "Log level: ${CELERY_WORKER_LOGLEVEL}"
echo "Prefetch multiplier: ${CELERY_WORKER_PREFETCH_MULTIPLIER:-1}"
echo "Max tasks per child: ${CELERY_WORKER_MAX_TASKS_PER_CHILD:-500}"
echo "Additional opts: ${CELERY_WORKER_OPTS:-none}"
echo "Note: Concurrency setting ignored with solo pool (always 1 task per worker)"

# Run celery worker in background
$CELERY_CMD &

# Store Celery worker PID
CELERY_PID=$!
echo "Celery worker started with PID: $CELERY_PID"

# Enhanced startup monitoring
echo ""
echo "=== Celery Worker Startup Monitoring ==="
for i in {1..10}; do
    if ! kill -0 $CELERY_PID 2>/dev/null; then
        echo "❌ Celery worker died after ${i} seconds!"
        wait $CELERY_PID
        EXIT_CODE=$?
        echo "Worker exit code: $EXIT_CODE"
        
        # Try to get more information about the failure
        echo ""
        echo "=== Failure Analysis ==="
        echo "Checking system resources..."
        free -h 2>/dev/null || echo "Memory info not available"
        df -h 2>/dev/null || echo "Disk info not available"
        echo "Checking for core dumps..."
        ls -la core* 2>/dev/null || echo "No core dumps found"
        
        exit $EXIT_CODE
    fi
    
    echo "Worker running... check $i/10 (PID: $CELERY_PID)"
    sleep 1
done

echo "✅ Celery worker is stable after 10 seconds"

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
    
    # Test if we can connect to our own worker  
    result = app.control.inspect().ping()
    if result:
        print('✅ Worker is responding to ping')
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

# Wait for Celery worker to exit and handle signals
wait $CELERY_PID

# Get the exit code
EXIT_CODE=$?
echo "Celery worker exited with code: $EXIT_CODE"

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