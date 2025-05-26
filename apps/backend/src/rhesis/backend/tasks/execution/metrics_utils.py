"""
Utility functions for managing metric configurations and behavior metrics.
"""

from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from rhesis.backend.app.models.metric import Metric
from rhesis.backend.logging.rhesis_logger import logger


def create_metric_config_from_model(metric: Metric) -> Optional[Dict]:
    """
    Convert a Metric model instance to a metric configuration dictionary.
    
    Args:
        metric: Metric model instance
        
    Returns:
        Dictionary containing the metric configuration
    """
    # Determine the backend type from backend_type relationship
    backend_raw = metric.backend_type.type_value if metric.backend_type else "deepeval"
    
    # Map specific custom metric types to supported backends
    backend_mapping = {
        "custom-code": "custom", 
        "custom-prompt": "custom",
        "framework": "deepeval"  # fallback for framework type
    }
    
    backend = backend_mapping.get(backend_raw, backend_raw)
    
    # Validate that we have essential metric information
    if not metric.class_name:
        logger.warning(f"Metric {metric.id} is missing class_name, skipping")
        return None
    
    # Get model and provider information if available
    provider = None
    model_name = None
    if metric.model and metric.model.provider_type:
        provider = metric.model.provider_type.type_value
        model_name = metric.model.model_name
    
    # Create the base metric config
    metric_config = {
        "name": metric.name or f"Metric_{metric.id}",
        "class_name": metric.class_name,
        "backend": backend,
        "threshold": metric.threshold if metric.threshold is not None else 0.5,
        "description": metric.description or f"Metric evaluation for {metric.class_name}",
        "parameters": {}
    }
    
    # Optional parameter mapping - only add parameters if they exist
    optional_params = {
        "evaluation_prompt": metric.evaluation_prompt,
        "evaluation_steps": metric.evaluation_steps,
        "reasoning": metric.reasoning,
        "min_score": metric.min_score,
        "max_score": metric.max_score
    }
    
    # Add all non-None optional parameters
    for param_name, param_value in optional_params.items():
        if param_value is not None:
            metric_config["parameters"][param_name] = param_value
            
    # Add model and provider if available
    if provider:
        metric_config["parameters"]["provider"] = provider
        
    if model_name:
        metric_config["parameters"]["model"] = model_name
    
    return metric_config


def get_behavior_metrics(db: Session, behavior_id: UUID) -> List[Dict]:
    """
    Retrieve metrics associated with a behavior.
    
    Args:
        db: Database session
        behavior_id: UUID of the behavior
        
    Returns:
        List of metric configurations
    """
    if not behavior_id:
        logger.warning("No behavior ID provided for metrics retrieval")
        return []
        
    try:
        # Query metrics related to the behavior
        metrics = db.query(Metric).join(
            Metric.behaviors
        ).filter(
            Metric.behaviors.any(id=behavior_id)
        ).all()
        
        # Convert to metric configs
        metric_configs = [
            config for config in 
            [create_metric_config_from_model(metric) for metric in metrics]
            if config is not None
        ]
        
        return metric_configs
        
    except Exception as e:
        logger.error(f"Error retrieving metrics for behavior {behavior_id}: {str(e)}", exc_info=True)
        return [] 