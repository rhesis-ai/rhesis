#!/bin/bash

# Print environment variables for debugging (excluding sensitive info)
echo "Environment Configuration:"
echo "BROKER_URL exists: $(if [ ! -z "$BROKER_URL" ]; then echo "yes"; else echo "no"; fi)"
echo "CELERY_RESULT_BACKEND exists: $(if [ ! -z "$CELERY_RESULT_BACKEND" ]; then echo "yes"; else echo "no"; fi)"
echo "SQLALCHEMY_DATABASE_URL exists: $(if [ ! -z "$SQLALCHEMY_DATABASE_URL" ]; then echo "yes"; else echo "no"; fi)"

# Start Celery worker with debug logging
celery -A rhesis.celery_app worker --loglevel=DEBUG &

# Store Celery worker PID
CELERY_PID=$!

# Start FastAPI server with debug logging
uvicorn rhesis.tasks.api:app --host 0.0.0.0 --port 8080 --log-level debug &

# Store FastAPI PID
UVICORN_PID=$!

# Function to forward signals to children
forward_signal() {
    kill -TERM $CELERY_PID
    kill -TERM $UVICORN_PID
}

# Set up signal handling
trap forward_signal SIGTERM SIGINT

# Wait for either process to exit
wait -n

# If either process exits, kill the other and exit with the same code
EXIT_CODE=$?
forward_signal
exit $EXIT_CODE 