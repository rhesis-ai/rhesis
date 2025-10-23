"""
Vertex AI Provider for Rhesis SDK

This provider enables access to Google's Vertex AI models (including Gemini) via LiteLLM.
It supports regional deployment and flexible credential management.

Available models:
    • gemini-2.5-flash
    • gemini-2.0-flash
    • gemini-2.0-flash-exp
    • gemini-1.5-pro-latest
    • gemini-pro

Environment Variables:
    Hybrid approach - supports multiple configuration methods:

    Method 1 - Base64 credentials (recommended for production/K8s):
        VERTEX_AI_CREDENTIALS: Base64-encoded service account JSON
        VERTEX_AI_ENDPOINT: Regional endpoint URL (e.g., https://europe-west3-aiplatform.googleapis.com)

    Method 2 - File path (recommended for local development):
        GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file
        VERTEX_AI_ENDPOINT: Regional endpoint URL

    Method 3 - File path with explicit region/project:
        GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file
        VERTEX_AI_LOCATION: GCP region (e.g., europe-west3)
        VERTEX_AI_PROJECT: GCP project ID (optional, extracted from credentials if not provided)

Usage:
    >>> # Using factory
    >>> from rhesis.sdk.models import get_model
    >>> model = get_model("vertex_ai")
    >>> result = model.generate("Hello from Vertex AI!")

    >>> # Direct instantiation
    >>> from rhesis.sdk.models.providers.vertex_ai import VertexAILLM
    >>> model = VertexAILLM(model_name="gemini-2.5-flash")
    >>> result = model.generate("Hello!", temperature=0.7)
"""

import base64
import json
import os
import re
import tempfile
from typing import Optional

from pydantic import BaseModel

from rhesis.sdk.models.providers.litellm import LiteLLM

PROVIDER = "vertex_ai"
DEFAULT_MODEL_NAME = "gemini-2.5-flash"


class VertexAILLM(LiteLLM):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, **kwargs):
        """
        VertexAILLM: Google Vertex AI LLM Provider

        This class provides an interface to Vertex AI models via LiteLLM with regional deployment support.

        Args:
            model_name (str): The name of the Vertex AI model to use (default: "gemini-2.5-flash").
            **kwargs: Additional parameters passed to the underlying LiteLLM completion call.

        Environment Variables (Hybrid Support):
            Method 1 - Base64 credentials (K8s/Production):
                VERTEX_AI_CREDENTIALS: Base64-encoded service account JSON
                VERTEX_AI_ENDPOINT: Regional endpoint URL

            Method 2 - File path with endpoint:
                GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file
                VERTEX_AI_ENDPOINT: Regional endpoint URL

            Method 3 - File path with explicit region:
                GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file
                VERTEX_AI_LOCATION: GCP region
                VERTEX_AI_PROJECT: GCP project ID (optional)

        Raises:
            ValueError: If credentials or configuration are not properly set.

        Examples:
            >>> llm = VertexAILLM(model_name="gemini-2.5-flash")
            >>> result = llm.generate("Tell me a joke.")
            >>> print(result)
        """
        # Store vertex AI configuration
        self._vertex_config = self._load_vertex_config()
        
        # Initialize parent LiteLLM with vertex_ai prefix
        # Don't pass api_key as Vertex AI uses credentials
        super().__init__(f"{PROVIDER}/{model_name}", api_key=None)
        
        # Store additional kwargs for later use
        self._extra_kwargs = kwargs

    def _load_vertex_config(self) -> dict:
        """
        Load Vertex AI configuration from environment variables.
        Supports multiple methods with priority order.
        
        Returns:
            dict: Configuration containing project, location, and credentials_path
        
        Raises:
            ValueError: If configuration is incomplete or invalid
        """
        config = {}
        
        # Step 1: Handle credentials (base64 or file path)
        vertex_creds_b64 = os.getenv("VERTEX_AI_CREDENTIALS")
        google_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if vertex_creds_b64:
            # Method 1: Base64-encoded credentials
            try:
                decoded_creds = base64.b64decode(vertex_creds_b64)
                creds_json = json.loads(decoded_creds)
                
                # Write to temporary file for LiteLLM
                temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                json.dump(creds_json, temp_file)
                temp_file.close()
                
                config['credentials_path'] = temp_file.name
                config['project'] = creds_json.get('project_id')
                config['_temp_file'] = temp_file.name  # Track for cleanup
                
            except Exception as e:
                raise ValueError(f"Failed to decode VERTEX_AI_CREDENTIALS: {e}")
                
        elif google_creds_path:
            # Method 2/3: File path
            if not os.path.exists(google_creds_path):
                raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS file not found: {google_creds_path}")
            
            config['credentials_path'] = google_creds_path
            
            # Extract project from credentials file
            try:
                with open(google_creds_path, 'r') as f:
                    creds_json = json.load(f)
                    config['project'] = creds_json.get('project_id')
            except Exception as e:
                raise ValueError(f"Failed to read credentials file: {e}")
        else:
            raise ValueError(
                "Vertex AI credentials not found. Set either:\n"
                "  - VERTEX_AI_CREDENTIALS (base64-encoded JSON), or\n"
                "  - GOOGLE_APPLICATION_CREDENTIALS (path to JSON file)"
            )
        
        # Step 2: Handle location/region
        vertex_endpoint = os.getenv("VERTEX_AI_ENDPOINT")
        vertex_location = os.getenv("VERTEX_AI_LOCATION")
        
        if vertex_endpoint:
            # Extract location from endpoint URL
            # e.g., https://europe-west3-aiplatform.googleapis.com -> europe-west3
            match = re.search(r'https://([^-]+(?:-[^-]+)*)-aiplatform\.googleapis\.com', vertex_endpoint)
            if match:
                config['location'] = match.group(1)
            else:
                raise ValueError(f"Could not extract region from VERTEX_AI_ENDPOINT: {vertex_endpoint}")
        elif vertex_location:
            # Explicit location provided
            config['location'] = vertex_location
        else:
            raise ValueError(
                "Vertex AI location not specified. Set either:\n"
                "  - VERTEX_AI_ENDPOINT (regional endpoint URL), or\n"
                "  - VERTEX_AI_LOCATION (region name like 'europe-west3')"
            )
        
        # Step 3: Handle project (can be overridden)
        vertex_project = os.getenv("VERTEX_AI_PROJECT")
        if vertex_project:
            config['project'] = vertex_project
        
        if not config.get('project'):
            raise ValueError("Could not determine VERTEX_AI_PROJECT from credentials or environment")
        
        return config

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[BaseModel] = None,
        *args,
        **kwargs,
    ):
        """
        Generate content using Vertex AI.
        
        This method overrides the parent to inject Vertex AI-specific parameters.
        
        Args:
            prompt: The text prompt
            system_prompt: Optional system prompt
            schema: Optional Pydantic schema for structured output
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        
        Returns:
            Generated text or dict (if schema provided)
        """
        # Inject Vertex AI parameters into kwargs
        vertex_kwargs = {
            'vertex_ai_project': self._vertex_config['project'],
            'vertex_ai_location': self._vertex_config['location'],
        }
        
        # Set credentials via environment variable for LiteLLM
        original_creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self._vertex_config['credentials_path']
        
        try:
            # Merge kwargs
            merged_kwargs = {**self._extra_kwargs, **kwargs, **vertex_kwargs}
            
            # Call parent generate method
            return super().generate(
                prompt=prompt,
                system_prompt=system_prompt,
                schema=schema,
                *args,
                **merged_kwargs
            )
        finally:
            # Restore original credentials environment variable
            if original_creds:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = original_creds
            elif 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
                del os.environ['GOOGLE_APPLICATION_CREDENTIALS']

    def __del__(self):
        """Cleanup temporary credentials file if created."""
        if hasattr(self, '_vertex_config') and '_temp_file' in self._vertex_config:
            temp_file = self._vertex_config['_temp_file']
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass  # Ignore cleanup errors

    def get_config_info(self) -> dict:
        """
        Get current Vertex AI configuration (useful for debugging).
        
        Returns:
            dict: Configuration details including project, location, and credentials source
        """
        return {
            'provider': PROVIDER,
            'model': self.model_name,
            'project': self._vertex_config['project'],
            'location': self._vertex_config['location'],
            'credentials_source': 'base64' if '_temp_file' in self._vertex_config else 'file',
            'credentials_path': self._vertex_config['credentials_path']
        }

