#!/bin/bash

# Exit on any error
set -e

# Print environment variables for debugging (excluding sensitive info)
echo "=== Environment Configuration Debug ==="
echo "BROKER_URL exists: $(if [ ! -z "$BROKER_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "CELERY_RESULT_BACKEND exists: $(if [ ! -z "$CELERY_RESULT_BACKEND" ]; then echo "yes"; else echo "no"; fi)"
echo "SQLALCHEMY_DATABASE_URL exists: $(if [ ! -z "$SQLALCHEMY_DATABASE_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "Celery worker concurrency: ${CELERY_WORKER_CONCURRENCY:-8}"
echo "Celery worker max tasks per child: ${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000}"
echo "Celery worker log level: ${CELERY_WORKER_LOGLEVEL:-INFO}"

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
echo "Available memory: $(free -h | grep Mem | awk '{print $7}' 2>/dev/null || echo 'N/A')"
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
    with app.connection() as conn:
        conn.connect()
        print('✅ Broker connection successful')
except Exception as e:
    print(f'❌ Broker connection failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
" || echo "⚠️ Broker connection test timed out or failed"

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

# Build the complete command
CELERY_CMD="celery -A rhesis.backend.worker.app worker --queues=celery,execution --loglevel=${CELERY_WORKER_LOGLEVEL:-INFO} --concurrency=${CELERY_WORKER_CONCURRENCY:-8} --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-4} --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000} ${CELERY_WORKER_OPTS}"

echo "Command: $CELERY_CMD"
echo "Queues: celery,execution"
echo "Log level: ${CELERY_WORKER_LOGLEVEL:-INFO}"
echo "Concurrency: ${CELERY_WORKER_CONCURRENCY:-8}"
echo "Prefetch multiplier: ${CELERY_WORKER_PREFETCH_MULTIPLIER:-4}"
echo "Max tasks per child: ${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000}"
echo "Additional opts: ${CELERY_WORKER_OPTS:-none}"

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

# Test worker connectivity
echo ""
echo "=== Worker Connectivity Test ==="
timeout 10 python -c "
import sys
try:
    from rhesis.backend.worker import app
    # Test if we can connect to our own worker
    result = app.control.inspect().ping()
    if result:
        print('✅ Worker is responding to ping')
        print(f'Active workers: {list(result.keys())}')
    else:
        print('⚠️ No workers responded to ping')
except Exception as e:
    print(f'❌ Worker connectivity test failed: {e}')
" || echo "⚠️ Worker connectivity test timed out"

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