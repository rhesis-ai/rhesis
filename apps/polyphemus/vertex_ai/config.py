"""Configuration for Vertex AI model deployments."""

import os
from typing import Any, TypedDict


class ModelConfig(TypedDict, total=False):
    """Configuration for a model deployment."""

    model_name: str
    model_id: str  # Can be HuggingFace ID or GCS path (gs://bucket/path)
    machine_type: str
    accelerator_type: str
    accelerator_count: int
    max_model_len: int
    hf_token: str  # Optional HuggingFace token for private models
    endpoint: Any  # aiplatform.Endpoint


# Environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
REGION = os.getenv("GCP_REGION", "us-central1")
SERVICE_ACCOUNT = os.getenv("GCP_SERVICE_ACCOUNT", "")

# GCS model path and default model (use existing GitHub secrets)
# MODEL_PATH e.g. gs://rhesis-model-bucket-dev/models
# DEFAULT_MODEL e.g. llama-3-1-8b-instruct
MODEL_PATH = os.getenv("MODEL_PATH", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "")

# Derived: bucket URI for staging (gs://bucket-name from MODEL_PATH)
# e.g. MODEL_PATH=gs://rhesis-model-bucket-dev/models -> BUCKET_URI=gs://rhesis-model-bucket-dev
BUCKET_URI = ""
if MODEL_PATH and MODEL_PATH.startswith("gs://"):
    parts = MODEL_PATH.split("/")
    if len(parts) >= 3:
        BUCKET_URI = f"gs://{parts[2]}"

# Full GCS path to default model for deployment
# e.g. MODEL_PATH + DEFAULT_MODEL -> gs://rhesis-model-bucket-dev/models/llama-3-1-8b-instruct
MODEL_GCS_PATH = ""
if MODEL_PATH and DEFAULT_MODEL:
    MODEL_GCS_PATH = f"{MODEL_PATH.rstrip('/')}/{DEFAULT_MODEL}"

# vLLM Docker image URI
# This is the official Vertex AI vLLM image
# Updated to match the notebook version
VLLM_DOCKER_URI = (
    "us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/"
    "pytorch-vllm-serve:20250710_0916_RC01"
)

# Default model configurations
# model_id can be:
#   1. HuggingFace model ID (e.g., "meta-llama/Meta-Llama-3.1-8B-Instruct")
#   2. GCS path (e.g., "gs://bucket-name/models/your-model")
#
# If MODEL_PATH and DEFAULT_MODEL are set, model_id is the full GCS path
MODELS: list[ModelConfig] = [
    {
        "model_name": DEFAULT_MODEL or "llama-3-1-8b-instruct",
        "model_id": MODEL_GCS_PATH or "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "machine_type": "g2-standard-12",
        "accelerator_type": "NVIDIA_L4",
        "accelerator_count": 1,
        "max_model_len": 4096,
        "hf_token": "",  # Optional: HuggingFace token for private models
    },
    # Example: Load from GCS bucket
    # {
    #     "model_name": "custom-model",
    #     "model_id": "gs://vllm-model-storage/models/custom-model",
    #     "machine_type": "g2-standard-12",
    #     "accelerator_type": "NVIDIA_L4",
    #     "accelerator_count": 1,
    #     "max_model_len": 4096,
    # },
]


def validate_config() -> None:
    """Validate that required configuration is set."""
    missing = []
    if not PROJECT_ID:
        missing.append("GCP_PROJECT_ID")
    if not SERVICE_ACCOUNT:
        missing.append("GCP_SERVICE_ACCOUNT")

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please set these variables before running the deployment script."
        )

    # Validate MODEL_PATH format if provided
    if MODEL_PATH and not MODEL_PATH.startswith("gs://"):
        raise ValueError(
            f"Invalid MODEL_PATH format: {MODEL_PATH}\n"
            "Must start with 'gs://' (e.g., gs://rhesis-model-bucket-dev/models)"
        )


def get_vllm_args(
    model_config: ModelConfig,
    enable_lora: bool = False,
    enforce_eager: bool = False,
    guided_decoding_backend: str = "auto",
) -> list[str]:
    """Build vLLM arguments for model deployment.

    Args:
        model_config: Model configuration dictionary
        enable_lora: Enable LoRA support
        enforce_eager: Enforce eager execution
        guided_decoding_backend: Guided decoding backend (auto, outlines, lm-format-enforcer)

    Returns:
        List of vLLM command line arguments
    """
    vllm_args = [
        "python",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--host=0.0.0.0",
        "--port=8080",
        f"--model={model_config['model_id']}",
        f"--tensor-parallel-size={model_config['accelerator_count']}",
        "--swap-space=16",
        "--gpu-memory-utilization=0.9",
        f"--max-model-len={model_config['max_model_len']}",
        "--dtype=auto",
        "--max-num-seqs=256",
        "--disable-log-stats",
        f"--guided-decoding-backend={guided_decoding_backend}",
    ]

    if enable_lora:
        vllm_args.extend(["--enable-lora", "--max-loras=1", "--max-cpu-loras=8"])

    if enforce_eager:
        vllm_args.append("--enforce-eager")

    return vllm_args
