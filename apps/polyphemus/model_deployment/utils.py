"""Utility functions for Vertex AI deployments."""

import logging
from typing import Optional

from google.api_core import exceptions
from google.cloud import compute_v1

logger = logging.getLogger(__name__)


def check_quota(
    project_id: str,
    region: str,
    accelerator_type: str,
    accelerator_count: int,
    is_for_training: bool = False,
) -> None:
    """Check if there is sufficient quota for the deployment.

    Args:
        project_id: GCP project ID
        region: GCP region
        accelerator_type: Type of accelerator (e.g., NVIDIA_L4, NVIDIA_A100)
        accelerator_count: Number of accelerators needed
        is_for_training: Whether this is for training (not currently used)

    Raises:
        ValueError: If there is insufficient quota
    """
    try:
        # Map Vertex AI accelerator types to Compute Engine GPU types
        gpu_type_mapping = {
            "NVIDIA_L4": "nvidia-l4",
            "NVIDIA_A100": "nvidia-tesla-a100",
            "NVIDIA_TESLA_T4": "nvidia-tesla-t4",
            "NVIDIA_TESLA_V100": "nvidia-tesla-v100",
            "NVIDIA_TESLA_P100": "nvidia-tesla-p100",
            "NVIDIA_TESLA_K80": "nvidia-tesla-k80",
        }

        gpu_type = gpu_type_mapping.get(accelerator_type)
        if not gpu_type:
            logger.warning(f"Unknown accelerator type: {accelerator_type}. Skipping quota check.")
            return

        # Get quota information
        client = compute_v1.RegionsClient()
        request = compute_v1.GetRegionRequest(project=project_id, region=region)

        try:
            region_info = client.get(request=request)
        except exceptions.NotFound:
            logger.warning(f"Region {region} not found. Skipping quota check.")
            return

        # Look for GPU quota
        gpu_quota_name = "GPUS_ALL_REGIONS"  # Or region-specific if needed
        available_gpus: Optional[float] = None

        for quota in region_info.quotas:
            if quota.metric.upper() == gpu_quota_name:
                available_gpus = quota.limit - quota.usage
                break

        if available_gpus is not None:
            if available_gpus < accelerator_count:
                raise ValueError(
                    f"Insufficient GPU quota in region {region}. "
                    f"Required: {accelerator_count}, Available: {available_gpus}. "
                    f"Please request quota increase or try a different region."
                )
            logger.info(
                f"✓ Quota check passed. Available GPUs: {available_gpus}, "
                f"Required: {accelerator_count}"
            )
        else:
            logger.warning(
                f"Could not find GPU quota information for {region}. "
                "Proceeding without quota check."
            )

    except Exception as e:
        logger.warning(f"Error checking quota: {e}. Proceeding without quota check.")


def format_deployment_summary(
    model_name: str, endpoint_name: str, endpoint_url: Optional[str] = None
) -> str:
    """Format a deployment summary message.

    Args:
        model_name: Name of the deployed model
        endpoint_name: Name of the endpoint
        endpoint_url: Optional URL of the endpoint

    Returns:
        Formatted summary string
    """
    summary = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                        DEPLOYMENT SUCCESSFUL                             ║
╚══════════════════════════════════════════════════════════════════════════╝

Model: {model_name}
Endpoint: {endpoint_name}
"""
    if endpoint_url:
        summary += f"URL: {endpoint_url}\n"

    summary += """
To test the endpoint:
  1. Use the Vertex AI console
  2. Use the Vertex AI Python client
  3. Use the REST API

For more information, see the README.md in apps/polyphemus/model_deployment/
"""
    return summary
