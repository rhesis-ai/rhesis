"""
Vertex AI Provider for Rhesis SDK

This provider enables access to Google's Vertex AI models (including Gemini) via LiteLLM.
It supports regional deployment and automatic credential detection (base64 or file path).

Available models (ordered by performance):
    • gemini-2.0-flash (RECOMMENDED - fastest, best for production)
    • gemini-2.0-flash-exp (experimental features)
    • gemini-2.5-flash (slower than 2.0, not recommended)
    • gemini-1.5-pro-latest
    • gemini-pro

Regional availability:
    • gemini-2.0-flash: Available in us-central1, us-east4, us-west1,
      europe-west1, europe-west4 (NOT in europe-west3)
    • gemini-2.5-flash: Available in all regions

For detailed usage and configuration options, see VertexAILLM class documentation.
"""

import base64
import json
import os
import tempfile
from typing import Optional

from pydantic import BaseModel

from rhesis.sdk.models.providers.litellm import LiteLLM

PROVIDER = "vertex_ai"
DEFAULT_MODEL_NAME = "gemini-2.0-flash"


class VertexAILLM(LiteLLM):
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        credentials: Optional[str] = None,
        location: Optional[str] = None,
        project: Optional[str] = None,
    ):
        """
        VertexAILLM: Google Vertex AI LLM Provider

        This class provides an interface to Vertex AI models via LiteLLM
        with regional deployment support and automatic credential detection.

        Args:
            model_name (str): The name of the Vertex AI model to use (default: "gemini-2.0-flash").
            credentials (Optional[str]): Service account credentials (auto-detected format)
                - Base64-encoded JSON string (for K8s/production)
                - Or file path to JSON file (standard for local development)
                - If not provided, uses GOOGLE_APPLICATION_CREDENTIALS environment variable
            location (Optional[str]): GCP region (e.g., "europe-west4" for Berlin)
                - If not provided, uses VERTEX_AI_LOCATION environment variable
            project (Optional[str]): GCP project ID (usually auto-extracted from credentials)
                - Priority: init parameter > VERTEX_AI_PROJECT env var > credentials file
                - If not provided, will be extracted from credentials file automatically

        Environment Variables (used as fallback):
            GOOGLE_APPLICATION_CREDENTIALS: Service account credentials
            VERTEX_AI_LOCATION: GCP region
            VERTEX_AI_PROJECT: (Optional) GCP project ID override

        Raises:
            ValueError: If credentials or configuration are not properly set.

        Examples:
            >>> # Using environment variables (recommended)
            >>> llm = VertexAILLM(model_name="gemini-2.0-flash")
            >>> result = llm.generate("Tell me a joke.")

            >>> # Passing credentials directly (for Berlin/Europe)
            >>> llm = VertexAILLM(
            ...     model_name="gemini-2.0-flash",
            ...     credentials="/path/to/service-account.json",
            ...     location="europe-west4",  # Netherlands - best for Europe
            ...     project="my-gcp-project"
            ... )
            >>> result = llm.generate("Tell me a joke.")
        """
        # Store initialization parameters
        self._init_credentials = credentials
        self._init_location = location
        self._init_project = project

        # Initialize parent LiteLLM with vertex_ai prefix
        # Don't pass api_key as Vertex AI uses credentials
        super().__init__(f"{PROVIDER}/{model_name}", api_key=None)

    def _load_credentials_from_base64(self, credentials: str) -> dict:
        """
        Attempt to load credentials from base64-encoded string.

        Args:
            credentials: Base64-encoded service account JSON

        Returns:
            dict: Config with credentials_path, project, and _temp_file

        Raises:
            Exception: If not valid base64 or JSON
        """
        decoded_credentials = base64.b64decode(credentials, validate=True)
        credentials_json = json.loads(decoded_credentials)

        # Write to temporary file for LiteLLM
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(credentials_json, temp_file)
        temp_file.close()

        return {
            "credentials_path": temp_file.name,
            "project": credentials_json.get("project_id"),
            "_temp_file": temp_file.name,
        }

    def _load_credentials_from_file(self, credentials: str) -> dict:
        """
        Load credentials from file path.

        Args:
            credentials: Path to service account JSON file

        Returns:
            dict: Config with credentials_path and project

        Raises:
            ValueError: If file doesn't exist or can't be read
        """
        if not os.path.exists(credentials):
            raise ValueError(f"Credentials file not found: {credentials}")

        with open(credentials, "r") as f:
            credentials_json = json.load(f)

        return {
            "credentials_path": credentials,
            "project": credentials_json.get("project_id"),
        }

    def _get_location(self) -> str:
        """
        Get Vertex AI location from initialization parameters or environment variables.
        Priority: init parameter > VERTEX_AI_LOCATION

        Returns:
            str: The GCP region/location

        Raises:
            ValueError: If location cannot be determined
        """
        # Check initialization parameter first
        if self._init_location:
            return self._init_location

        # Try environment variable
        vertex_location = os.getenv("VERTEX_AI_LOCATION")
        if vertex_location:
            return vertex_location

        raise ValueError(
            "Vertex AI location not specified. Provide either:\n"
            "  - location parameter in __init__, or\n"
            "  - VERTEX_AI_LOCATION environment variable (e.g., 'europe-west4', 'us-central1')"
        )

    def _load_credentials(self, credentials: str) -> dict:
        """
        Load credentials by trying different methods in sequence.

        Args:
            credentials: Either base64-encoded JSON or file path

        Returns:
            dict: Config with credentials_path and project

        Raises:
            ValueError: If all methods fail
        """
        # Try base64 first
        try:
            return self._load_credentials_from_base64(credentials)
        except Exception:
            pass

        # Try file path
        try:
            return self._load_credentials_from_file(credentials)
        except Exception:
            pass

        # All methods failed
        raise ValueError(
            f"GOOGLE_APPLICATION_CREDENTIALS is neither valid base64 nor an existing file path: "
            f"{credentials}"
        )

    def load_model(self) -> dict:
        """
        Load Vertex AI configuration from initialization parameters or environment variables.

        Note: This method is named 'load_model' to comply with the BaseLLM abstract interface,
        but for Vertex AI (a remote API), we're loading configuration rather than a model.
        The returned config is stored in self.model and used throughout the provider.

        Priority: init parameters > environment variables
        Automatically detects if credentials are base64-encoded or a file path.

        Returns:
            dict: Configuration containing project, location, and credentials_path
                This dict is stored in self.model and accessed by generate() and other methods.

        Raises:
            ValueError: If configuration is incomplete or invalid
        """
        # Step 1: Get credentials (init parameter takes priority)
        google_credentials = self._init_credentials or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not google_credentials:
            raise ValueError(
                "GOOGLE_APPLICATION_CREDENTIALS not found. Provide either:\n"
                "  - credentials parameter in __init__, or\n"
                "  - GOOGLE_APPLICATION_CREDENTIALS environment variable\n"
                "Value can be base64-encoded JSON or file path to service account JSON"
            )

        # Step 2: Load credentials (auto-detect format and normalize to file path)
        # This also extracts project_id from the credentials file
        config = self._load_credentials(google_credentials)

        # Step 3: Get location (init parameter takes priority)
        config["location"] = self._get_location()

        # Step 4: Set project with priority order
        # Priority: init parameter > env variable > credentials file (already in config)
        if self._init_project:
            # Override with init parameter
            config["project"] = self._init_project
        elif os.getenv("VERTEX_AI_PROJECT"):
            # Override with environment variable
            config["project"] = os.getenv("VERTEX_AI_PROJECT")
        # Else: keep project from credentials file (already set in config from step 2)

        # Verify we have a project from at least one source
        if not config.get("project"):
            raise ValueError(
                "Could not determine VERTEX_AI_PROJECT. Provide either:\n"
                "  - project parameter in __init__, or\n"
                "  - VERTEX_AI_PROJECT environment variable, or\n"
                "  - Ensure project_id is in credentials file"
            )

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
        # Inject Vertex AI-specific parameters
        kwargs["vertex_ai_project"] = self.model["project"]
        kwargs["vertex_ai_location"] = self.model["location"]

        # Set credentials via environment variable for LiteLLM
        original_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.model["credentials_path"]

        try:
            # Call parent generate method
            return super().generate(
                prompt=prompt, system_prompt=system_prompt, schema=schema, *args, **kwargs
            )
        finally:
            # Restore original credentials environment variable
            if original_credentials:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = original_credentials
            elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
                del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

    def __del__(self):
        """Cleanup temporary credentials file if created."""
        if hasattr(self, "model") and isinstance(self.model, dict) and "_temp_file" in self.model:
            temp_file = self.model["_temp_file"]
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
            "provider": PROVIDER,
            "model": self.model_name,
            "project": self.model["project"],
            "location": self.model["location"],
            "credentials_source": "base64" if "_temp_file" in self.model else "file",
            "credentials_path": self.model["credentials_path"],
        }
