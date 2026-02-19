"""Main deployment script for deploying models to Vertex AI."""

import logging
from typing import Optional, Tuple

from google.cloud import aiplatform

from .config import (
    BUCKET_URI,
    DEFAULT_MODEL,
    MODEL_GCS_PATH,
    MODEL_PATH,
    MODELS,
    PROJECT_ID,
    REGION,
    SERVICE_ACCOUNT,
    VLLM_DOCKER_URI,
    ModelConfig,
    get_endpoint_display_name,
    get_model_registry_display_name,
    get_vllm_args,
    validate_config,
)
from .utils import check_quota, format_deployment_summary

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def deploy_model_vllm(
    model_config: ModelConfig,
    service_account: str,
    enable_lora: bool = False,
    enforce_eager: bool = False,
    guided_decoding_backend: str = "auto",
) -> Tuple[aiplatform.Model, aiplatform.Endpoint]:
    """Deploy a model with vLLM on Vertex AI.

    Args:
        model_config: Model configuration dictionary
        service_account: Service account email for deployment
        enable_lora: Enable LoRA support
        enforce_eager: Enforce eager execution
        guided_decoding_backend: Guided decoding backend

    Returns:
        Tuple of (Model, Endpoint) objects

    Raises:
        ValueError: If quota is insufficient or deployment fails
    """
    # Check quota before deploying
    check_quota(
        project_id=PROJECT_ID,
        region=REGION,
        accelerator_type=model_config["accelerator_type"],
        accelerator_count=model_config["accelerator_count"],
        is_for_training=False,
    )

    # Build vLLM arguments
    vllm_args = get_vllm_args(
        model_config=model_config,
        enable_lora=enable_lora,
        enforce_eager=enforce_eager,
        guided_decoding_backend=guided_decoding_backend,
    )

    logger.info(f"Uploading model: {model_config['model_name']}")
    logger.info(f"Model ID: {model_config['model_id']}")
    logger.info(f"vLLM arguments: {' '.join(vllm_args)}")

    # Prepare environment variables
    env_vars = {
        "MODEL_ID": model_config["model_id"],
        "DEPLOY_SOURCE": "polyphemus",
    }

    # Add HuggingFace token if provided (for private models)
    hf_token = model_config.get("hf_token", "")
    if hf_token:
        env_vars["HF_TOKEN"] = hf_token
        logger.info("HuggingFace token provided for private model access")

    # Upload model (registry name: polyphemus-dev / polyphemus-stg / polyphemus by env)
    model = aiplatform.Model.upload(
        display_name=get_model_registry_display_name(),
        serving_container_image_uri=VLLM_DOCKER_URI,
        serving_container_args=vllm_args,
        serving_container_ports=[8080],
        serving_container_predict_route="/v1/chat/completions",
        serving_container_health_route="/ping",
        serving_container_environment_variables=env_vars,
        serving_container_shared_memory_size_mb=(16 * 1024),  # 16GB
        serving_container_deployment_timeout=7200,  # 2 hours
    )

    logger.info(f"Model uploaded successfully: {model.resource_name}")
    logger.info(f"Deploying {model_config['model_name']} to endpoint...")

    # Get the endpoint from model_config (must be set before calling this function)
    endpoint = model_config.get("endpoint")
    if endpoint is None:
        raise ValueError(
            f"Endpoint not set for model {model_config['model_name']}. "
            "Call get_or_create_endpoint() first."
        )

    # Deploy to endpoint
    model.deploy(
        endpoint=endpoint,
        machine_type=model_config["machine_type"],
        accelerator_type=model_config["accelerator_type"],
        accelerator_count=model_config["accelerator_count"],
        deploy_request_timeout=1800,  # 30 minutes
        service_account=service_account,
    )

    logger.info(f"✓ Successfully deployed {model_config['model_name']}")
    return model, endpoint


def get_or_create_endpoint(
    model_config: ModelConfig, force_create: bool = False
) -> aiplatform.Endpoint:
    """Get an existing endpoint or create a new one.

    Endpoint display name is environment-based: polyphemus-endpoint-dev,
    polyphemus-endpoint-stg, or polyphemus-endpoint (prd).

    Args:
        model_config: Model configuration dictionary
        force_create: Force creation of a new endpoint even if one exists

    Returns:
        Endpoint object
    """
    endpoint_name = get_endpoint_display_name()

    if not force_create:
        # Try to find existing endpoint
        endpoints = aiplatform.Endpoint.list(
            filter=f'display_name="{endpoint_name}"', order_by="create_time desc"
        )

        if endpoints:
            endpoint = endpoints[0]
            logger.info(f"✓ Retrieved existing endpoint: {endpoint_name}")

            # Check if already deployed
            deployed_models = endpoint.list_models()
            if deployed_models:
                logger.info(
                    f"⊘ Endpoint {endpoint_name} already has deployed models. "
                    f"Found {len(deployed_models)} model(s)."
                )
                for deployed_model in deployed_models:
                    logger.info(f"  - {deployed_model.display_name}")

            return endpoint

    # Create new endpoint
    logger.info(f"Creating new endpoint: {endpoint_name}")
    endpoint = aiplatform.Endpoint.create(display_name=endpoint_name)
    logger.info(f"✓ Created endpoint: {endpoint_name}")
    return endpoint


def deploy_models(
    models: Optional[list[ModelConfig]] = None,
    service_account: Optional[str] = None,
    skip_existing: bool = True,
    enable_lora: bool = False,
    enforce_eager: bool = False,
    guided_decoding_backend: str = "auto",
) -> None:
    """Deploy multiple models to Vertex AI.

    Args:
        models: List of model configurations (defaults to MODELS from config)
        service_account: Service account email (defaults to SERVICE_ACCOUNT from config)
        skip_existing: Skip models that are already deployed
        enable_lora: Enable LoRA support
        enforce_eager: Enforce eager execution
        guided_decoding_backend: Guided decoding backend
    """
    # Validate configuration
    validate_config()

    # Initialize Vertex AI with bucket if provided
    init_kwargs = {"project": PROJECT_ID, "location": REGION}
    if BUCKET_URI:
        # Use a temporal subdirectory in the bucket for Vertex AI artifacts (env-agnostic)
        bucket_uri = f"{BUCKET_URI}/temporal"
        init_kwargs["staging_bucket"] = bucket_uri  # Vertex AI SDK parameter name
        logger.info(f"Using GCS bucket for Vertex AI: {bucket_uri}")

    aiplatform.init(**init_kwargs)
    logger.info(f"Initialized Vertex AI: project={PROJECT_ID}, region={REGION}")

    # Log GCS configuration if provided
    if MODEL_PATH:
        logger.info(f"Model path (MODEL_PATH): {MODEL_PATH}")
    if DEFAULT_MODEL:
        logger.info(f"Default model (DEFAULT_MODEL): {DEFAULT_MODEL}")
    if MODEL_GCS_PATH:
        logger.info(f"Full model GCS path: {MODEL_GCS_PATH}")
    if BUCKET_URI:
        logger.info(f"bucket: {BUCKET_URI}")

    # Use defaults if not provided
    if models is None:
        models = MODELS
    if service_account is None:
        service_account = SERVICE_ACCOUNT

    if not models:
        logger.warning("No models configured for deployment.")
        return

    logger.info(f"Deploying {len(models)} model(s) to Vertex AI...")

    deployed_count = 0
    skipped_count = 0

    for model_config in models:
        model_name = model_config["model_name"]
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Processing model: {model_name}")
        logger.info(f"{'=' * 80}")

        try:
            # Get or create endpoint
            endpoint = get_or_create_endpoint(model_config)
            model_config["endpoint"] = endpoint

            # Check if already deployed
            if skip_existing:
                deployed_models = endpoint.list_models()
                if deployed_models:
                    logger.info(f"⊘ Skipping {model_name} - already deployed to endpoint\n")
                    skipped_count += 1
                    continue

            # Deploy model
            logger.info(f"→ Deploying {model_name}...")
            deploy_model_vllm(
                model_config=model_config,
                service_account=service_account,
                enable_lora=enable_lora,
                enforce_eager=enforce_eager,
                guided_decoding_backend=guided_decoding_backend,
            )

            # Print deployment summary
            print(
                format_deployment_summary(
                    model_name=model_name,
                    endpoint_name=get_endpoint_display_name(),
                    endpoint_url=endpoint.resource_name,
                )
            )

            deployed_count += 1

        except Exception as e:
            logger.error(f"❌ Failed to deploy {model_name}: {e}", exc_info=True)
            continue

    # Final summary
    logger.info(f"\n{'=' * 80}")
    logger.info("DEPLOYMENT SUMMARY")
    logger.info(f"{'=' * 80}")
    logger.info(f"Total models: {len(models)}")
    logger.info(f"Deployed: {deployed_count}")
    logger.info(f"Skipped: {skipped_count}")
    logger.info(f"Failed: {len(models) - deployed_count - skipped_count}")


def main():
    """Main entry point for the deployment script."""
    import argparse

    parser = argparse.ArgumentParser(description="Deploy models to Vertex AI with vLLM")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip models that are already deployed (default: True)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force deployment even if models are already deployed",
    )
    parser.add_argument("--enable-lora", action="store_true", help="Enable LoRA support")
    parser.add_argument("--enforce-eager", action="store_true", help="Enforce eager execution")
    parser.add_argument(
        "--guided-decoding-backend",
        type=str,
        default="auto",
        choices=["auto", "outlines", "lm-format-enforcer"],
        help="Guided decoding backend (default: auto)",
    )

    args = parser.parse_args()

    deploy_models(
        skip_existing=args.skip_existing and not args.force,
        enable_lora=args.enable_lora,
        enforce_eager=args.enforce_eager,
        guided_decoding_backend=args.guided_decoding_backend,
    )


if __name__ == "__main__":
    main()
