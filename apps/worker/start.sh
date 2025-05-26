#!/bin/bash

# Print environment variables for debugging (excluding sensitive info)
echo "Environment Configuration:"
echo "BROKER_URL exists: $(if [ ! -z "$BROKER_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "CELERY_RESULT_BACKEND exists: $(if [ ! -z "$CELERY_RESULT_BACKEND" ]; then echo "yes"; else echo "no"; fi)"
echo "SQLALCHEMY_DATABASE_URL exists: $(if [ ! -z "$SQLALCHEMY_DATABASE_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "Celery worker concurrency: ${CELERY_WORKER_CONCURRENCY:-8}"
echo "Celery worker max tasks per child: ${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000}"
echo "Celery worker log level: ${CELERY_WORKER_LOGLEVEL:-INFO}"

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

# Start Celery worker with configuration from environment variables
echo "Starting Celery worker..."
celery -A rhesis.backend.worker.app worker \
    --loglevel=${CELERY_WORKER_LOGLEVEL:-INFO} \
    --concurrency=${CELERY_WORKER_CONCURRENCY:-8} \
    --prefetch-multiplier=${CELERY_WORKER_PREFETCH_MULTIPLIER:-4} \
    --max-tasks-per-child=${CELERY_WORKER_MAX_TASKS_PER_CHILD:-1000} \
    ${CELERY_WORKER_OPTS} &

# Store Celery worker PID
CELERY_PID=$!
echo "Celery worker started with PID: $CELERY_PID"

# Function to forward signals to children
forward_signal() {
    echo "Received shutdown signal, stopping processes..."
    
    if [ ! -z "$HEALTH_SERVER_PID" ]; then
        echo "Stopping health check server (PID: $HEALTH_SERVER_PID)..."
        kill -TERM $HEALTH_SERVER_PID || true
    fi
    
    if [ ! -z "$FLOWER_PID" ]; then
        echo "Stopping Flower (PID: $FLOWER_PID)..."
        kill -TERM $FLOWER_PID || true
    fi
    
    echo "Stopping Celery worker (PID: $CELERY_PID)..."
    kill -TERM $CELERY_PID || true
}

# Set up signal handling
trap forward_signal SIGTERM SIGINT

# Wait for Celery worker to exit
wait $CELERY_PID

# Exit with Celery's exit code
EXIT_CODE=$?
echo "Celery worker exited with code: $EXIT_CODE"

# If health server is running, stop it
if [ ! -z "$HEALTH_SERVER_PID" ]; then
    if kill -0 $HEALTH_SERVER_PID 2>/dev/null; then
        echo "Stopping health check server..."
        kill -TERM $HEALTH_SERVER_PID
        wait $HEALTH_SERVER_PID || true
    fi
fi

# If Flower is running, stop it
if [ ! -z "$FLOWER_PID" ]; then
    # Check if flower is still running
    if kill -0 $FLOWER_PID 2>/dev/null; then
        echo "Stopping Flower monitoring..."
        kill -TERM $FLOWER_PID
        wait $FLOWER_PID || true
    fi
fi

exit $EXIT_CODE 