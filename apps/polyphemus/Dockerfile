# Start with NVIDIA CUDA base image with more recent CUDA version
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    wget \
    apt-utils \
    && rm -rf /var/lib/apt/lists/*

# Create and use virtual environment
RUN python3 -m venv $VIRTUAL_ENV

# Create a non-root user to run the app
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install basic build dependencies first (within venv)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir packaging wheel setuptools

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies in venv
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu121 -r requirements.txt

# Install flash-attn separately with a specific pre-built wheel for CUDA 12.1
# Directly using a compatible wheel URL to avoid compilation
RUN pip install --no-cache-dir "https://github.com/Dao-AILab/flash-attention/releases/download/v2.3.3/flash_attn-2.3.3+cu122torch2.1cxx11abiFALSE-cp310-cp310-linux_x86_64.whl"

# Copy the application code
COPY . .

# Environment variables for HF model
ENV HF_MODEL="cognitivecomputations/Dolphin3.0-Llama3.1-8B"
ENV HF_TOKEN=""

# For caching models (optional)
ENV TRANSFORMERS_CACHE="/app/model_cache"
RUN mkdir -p /app/model_cache && chown -R appuser:appuser /app

# Expose the port the app will run on
EXPOSE 8080

# Switch to non-root user
USER appuser

# Start the FastAPI app using Gunicorn with optimized settings
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "3600", "--worker-class", "uvicorn.workers.UvicornWorker", "polyphemus.main:app", "--preload"]