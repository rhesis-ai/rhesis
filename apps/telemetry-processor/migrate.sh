#!/bin/bash
# Database migration script for telemetry processor

set -e

echo "🔄 Running analytics database migrations..."

# Run migrations
alembic upgrade head

echo "✅ Analytics database migrations completed successfully"

