#!/bin/bash

# Exit on any error
set -e

# Print environment variables for debugging (excluding sensitive info)
echo "Environment Configuration:"
echo "BROKER_URL exists: $(if [ ! -z "$BROKER_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "CELERY_RESULT_BACKEND exists: $(if [ ! -z "$CELERY_RESULT_BACKEND" ]; then echo "yes"; else echo "no"; fi)"
echo "SQLALCHEMY_DATABASE_URL exists: $(if [ ! -z "$SQLALCHEMY_DATABASE_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "Celery worker concurrency: ${CELERY_WORKER_CONCURRENCY:-8}"
echo "Celery worker max tasks per child: ${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000}"
echo "Celery worker log level: ${CELERY_WORKER_LOGLEVEL:-INFO}"

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
timeout 10 python -c "
import sys
try:
    from rhesis.backend.worker import app
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
echo "Starting Celery worker with full output..."
echo "Command: celery -A rhesis.backend.worker.app worker --loglevel=${CELERY_WORKER_LOGLEVEL:-INFO} --concurrency=${CELERY_WORKER_CONCURRENCY:-8} --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-4} --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000} ${CELERY_WORKER_OPTS}"

# Run celery worker in foreground first to see any immediate errors
celery -A rhesis.backend.worker.app worker \
    --queues=celery,execution \
    --loglevel=${CELERY_WORKER_LOGLEVEL:-INFO} \
    --concurrency=${CELERY_WORKER_CONCURRENCY:-8} \
    --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-4} \
    --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000} \
    ${CELERY_WORKER_OPTS} &

# Store Celery worker PID
CELERY_PID=$!
echo "Celery worker started with PID: $CELERY_PID"

# Wait a moment and check if the worker is still running
sleep 5
if ! kill -0 $CELERY_PID 2>/dev/null; then
    echo "❌ Celery worker died immediately after startup!"
    wait $CELERY_PID
    EXIT_CODE=$?
    echo "Worker exit code: $EXIT_CODE"
    exit $EXIT_CODE
else
    echo "✅ Celery worker is running after 5 seconds"
fi

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