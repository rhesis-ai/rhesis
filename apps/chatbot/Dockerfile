# Hint: Build this image with an expanded build context
# `docker build -t rhesis-backend -f backend/Dockerfile .`

# First stage: Build dependencies
FROM python:3.9-slim AS builder

WORKDIR /app

# Install build dependencies including PostgreSQL development files
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from the bot directory
COPY bot/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Second stage: Run the application
FROM python:3.9-slim

WORKDIR /app

# Install runtime dependencies first
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install gunicorn
RUN pip install --no-cache-dir gunicorn

# Copy dependencies from builder (changes less frequently than app code)
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Create a non-root user before copying app code
RUN adduser --disabled-password --gecos '' rhesis-user

# Copy the entire bot directory
COPY bot /app/bot

# Remove any existing .env files to prevent environment variable conflicts
RUN find /app -name ".env" -type f -delete

# Set ownership after copying app code
RUN chown -R rhesis-user /app

# Switch to the non-root user
USER rhesis-user

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Expose port
EXPOSE 8080

# Command to run the FastAPI application with Gunicorn
CMD ["gunicorn", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "bot.client:app"]