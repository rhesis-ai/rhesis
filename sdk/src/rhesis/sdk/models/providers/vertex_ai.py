"""
Vertex AI Provider for Rhesis SDK

This provider enables access to Google's Vertex AI models (including Gemini) via LiteLLM.
It supports regional deployment and automatic credential detection (base64 or file path).


Regional availability:
    • gemini-2.0-flash: Available in us-central1, us-east4, us-west1,
      europe-west1, europe-west4 (NOT in europe-west3)
    • gemini-2.5-flash: Available in all regions

For detailed usage and configuration options, see VertexAILLM class documentation.
"""

import base64
import json
import logging
import os
from typing import List, Optional, Type, Union

from pydantic import BaseModel

from rhesis.sdk.models.base import Embedding
from rhesis.sdk.models.defaults import (
    DEFAULT_EMBEDDING_MODELS,
    DEFAULT_LANGUAGE_MODELS,
    model_name_from_id,
)
from rhesis.sdk.models.providers.litellm import LiteLLM, LiteLLMEmbedder

logger = logging.getLogger(__name__)

DEFAULT_MODEL = DEFAULT_LANGUAGE_MODELS["vertex_ai"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)
DEFAULT_EMBEDDING_MODEL = model_name_from_id(DEFAULT_EMBEDDING_MODELS["vertex_ai"])


class VertexAICredentialsMixin:
    """Mixin class providing Vertex AI credential handling.

    This mixin contains shared credential loading and configuration logic
    used by both VertexAILLM and VertexAIEmbedder.
    """

    _init_credentials: Optional[str]
    _init_location: Optional[str]
    _init_project: Optional[str]
    _original_credentials_env: Optional[str]
    _vertex_config: dict

    def _init_vertex_credentials(
        self,
        credentials: Optional[str] = None,
        location: Optional[str] = None,
        project: Optional[str] = None,
    ):
        """Initialize Vertex AI credential attributes.

        Args:
            credentials: Service account credentials (base64 or file path)
            location: GCP region
            project: GCP project ID
        """
        self._init_credentials = credentials
        self._init_location = location
        self._init_project = project
        self._original_credentials_env = credentials or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    def _load_credentials_from_base64(self, credentials: str) -> dict:
        """
        Decode base64-encoded service account credentials and return as
        a JSON string suitable for LiteLLM's ``vertex_credentials`` parameter.

        No temporary files are created; the credentials stay in memory.

        Args:
            credentials: Base64-encoded service account JSON

        Returns:
            dict: Config with vertex_credentials (JSON string) and project

        Raises:
            Exception: If not valid base64 or JSON
        """
        decoded_credentials = base64.b64decode(credentials, validate=True)
        credentials_json = json.loads(decoded_credentials)

        return {
            "vertex_credentials": json.dumps(credentials_json),
            "credentials_source": "base64",
            "project": credentials_json.get("project_id"),
        }

    def _load_credentials_from_file(self, credentials: str) -> dict:
        """
        Load credentials from a file path.  LiteLLM accepts file paths
        directly via ``vertex_credentials``, so we just validate and
        extract the project_id without writing anything.

        Args:
            credentials: Path to service account JSON file

        Returns:
            dict: Config with vertex_credentials (file path) and project

        Raises:
            ValueError: If file doesn't exist or can't be read
        """
        if not os.path.exists(credentials):
            raise ValueError(f"Credentials file not found: {credentials}")

        try:
            with open(credentials, "r") as f:
                credentials_json = json.load(f)
        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to read credentials file {credentials}: {e}")

        return {
            "vertex_credentials": credentials,
            "credentials_source": "file",
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
            dict: Config with vertex_credentials and project

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

        # All methods failed.  Include the value only when it looks like a file
        # path (starts with "/" or "./") — file paths are not secrets.  Omit
        # the value otherwise (e.g. base64 blobs) to avoid leaking credentials.
        looks_like_path = credentials.startswith("/") or credentials.startswith("./")
        detail = f" (path: {credentials})" if looks_like_path else ""
        raise ValueError(
            f"GOOGLE_APPLICATION_CREDENTIALS could not be loaded{detail}: "
            "value is neither valid base64-encoded JSON nor an existing file path."
        )

    def _load_vertex_config(self) -> dict:
        """
        Load Vertex AI configuration from initialization parameters or environment variables.

        Priority: init parameters > environment variables
        Automatically detects if credentials are base64-encoded or a file path.

        Returns:
            dict: Configuration containing project, location, and vertex_credentials

        Raises:
            ValueError: If configuration is incomplete or invalid
        """
        google_credentials = self._original_credentials_env
        if not google_credentials:
            raise ValueError(
                "GOOGLE_APPLICATION_CREDENTIALS not found. Provide either:\n"
                "  - credentials parameter in __init__, or\n"
                "  - GOOGLE_APPLICATION_CREDENTIALS environment variable\n"
                "Value can be base64-encoded JSON or file path to service account JSON"
            )

        config = self._load_credentials(google_credentials)

        config["location"] = self._get_location()

        if self._init_project:
            config["project"] = self._init_project
        elif os.getenv("VERTEX_AI_PROJECT"):
            config["project"] = os.getenv("VERTEX_AI_PROJECT")

        if not config.get("project"):
            raise ValueError(
                "Could not determine VERTEX_AI_PROJECT. Provide either:\n"
                "  - project parameter in __init__, or\n"
                "  - VERTEX_AI_PROJECT environment variable, or\n"
                "  - Ensure project_id is in credentials file"
            )

        return config


class VertexAILLM(VertexAICredentialsMixin, LiteLLM):
    PROVIDER = "vertex_ai"

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
        # Initialize credential handling from mixin
        self._init_vertex_credentials(credentials, location, project)

        # Initialize parent LiteLLM with vertex_ai prefix
        # Don't pass api_key as Vertex AI uses credentials
        super().__init__(f"{self.PROVIDER}/{model_name}", api_key=None)

    def load_model(self) -> dict:
        """
        Load Vertex AI configuration from initialization parameters or environment variables.

        Note: This method is named 'load_model' to comply with the BaseLLM abstract interface,
        but for Vertex AI (a remote API), we're loading configuration rather than a model.
        The returned config is stored in self.model and used throughout the provider.

        Returns:
            dict: Configuration containing project, location, and vertex_credentials
        """
        self._vertex_config = self._load_vertex_config()
        return self._vertex_config

    async def a_generate(
        self,
        prompt: str = "",
        system_prompt: Optional[str] = None,
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        *args,
        **kwargs,
    ):
        """
        Generate content using Vertex AI (async).

        Overrides the parent to inject Vertex AI-specific parameters.
        Called directly via ``await model.a_generate(...)`` or indirectly
        through ``model.generate(...)`` which bridges via ``run_sync()``.

        Args:
            prompt: The text prompt (ignored when ``messages`` is provided
                via ``**kwargs``)
            system_prompt: Optional system prompt
            schema: Optional Pydantic schema for structured output
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments (including ``messages``
                for multi-turn conversations)

        Returns:
            Generated text or dict (if schema provided)
        """
        kwargs["vertex_ai_project"] = self.model["project"]
        kwargs["vertex_ai_location"] = self.model["location"]
        kwargs["vertex_credentials"] = self.model["vertex_credentials"]

        return await super().a_generate(
            prompt=prompt,
            system_prompt=system_prompt,
            schema=schema,
            *args,
            **kwargs,
        )

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        n: int = 1,
        *args,
        **kwargs,
    ) -> List[Union[str, dict]]:
        """
        Generate batch content using Vertex AI.

        This method overrides the parent to inject Vertex AI-specific parameters.

        Args:
            prompts: List of user prompts
            system_prompt: Optional system prompt (applied to all prompts)
            schema: Optional Pydantic schema for structured output
            n: Number of completions to generate per prompt
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            List of generated text or dicts (if schema provided)
        """
        kwargs["vertex_ai_project"] = self.model["project"]
        kwargs["vertex_ai_location"] = self.model["location"]
        kwargs["vertex_credentials"] = self.model["vertex_credentials"]

        return super().generate_batch(
            prompts=prompts,
            system_prompt=system_prompt,
            schema=schema,
            n=n,
            *args,
            **kwargs,
        )

    async def warmup(self) -> None:
        """Pre-warm LiteLLM's VertexAI credential cache before concurrent use.

        LiteLLM's module-level ``vertex_chat_completion`` singleton fetches an OAuth
        token on the first call via ``_ensure_access_token_async``.  Without a warm-up,
        every coroutine in an ``asyncio.gather`` batch races to fetch the token
        simultaneously, each spawning its own thread and making redundant HTTPS calls.

        One sequential warm-up call here populates ``_credentials_project_mapping`` in
        the singleton so every subsequent concurrent call returns the cached token
        immediately.
        """
        try:
            from litellm.main import vertex_chat_completion

            project = (self.model or {}).get("project")
            await vertex_chat_completion._ensure_access_token_async(
                credentials=self.model["vertex_credentials"],
                project_id=project,
                custom_llm_provider="vertex_ai",
            )
            logger.debug("VertexAI credentials pre-warmed (LiteLLM cache populated)")
        except Exception as e:
            logger.warning(f"VertexAI credential pre-warm failed (non-fatal, proceeding): {e}")

    def get_config_info(self) -> dict:
        """
        Get current Vertex AI configuration (useful for debugging).

        Returns:
            dict: Configuration details including project, location, and credentials source
        """
        return {
            "provider": self.PROVIDER,
            "model": self.model_name,
            "project": self.model["project"],
            "location": self.model["location"],
            "credentials_source": self.model.get("credentials_source", "unknown"),
        }


class VertexAIEmbedder(VertexAICredentialsMixin, LiteLLMEmbedder):
    """Vertex AI embedder using Google's text-embedding models.

    This class provides an interface for generating embeddings using Vertex AI
    with regional deployment support and automatic credential detection.

    Args:
        model_name: The embedding model name (default: "text-embedding-005").
        credentials: Service account credentials (auto-detected format)
            - Base64-encoded JSON string (for K8s/production)
            - Or file path to JSON file (standard for local development)
            - If not provided, uses GOOGLE_APPLICATION_CREDENTIALS environment variable
        location: GCP region (e.g., "europe-west4")
            - If not provided, uses VERTEX_AI_LOCATION environment variable
        project: GCP project ID (usually auto-extracted from credentials)
            - Priority: init parameter > VERTEX_AI_PROJECT env var > credentials file
        dimensions: Optional embedding dimensions (supported by text-embedding-005).

    Environment Variables (used as fallback):
        GOOGLE_APPLICATION_CREDENTIALS: Service account credentials
        VERTEX_AI_LOCATION: GCP region
        VERTEX_AI_PROJECT: (Optional) GCP project ID override

    Usage:
        >>> embedder = VertexAIEmbedder()
        >>> embedding = embedder.generate("Hello, world!")
        >>> embeddings = embedder.generate_batch(["Hello", "World"])
    """

    PROVIDER = "vertex_ai"

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        credentials: Optional[str] = None,
        location: Optional[str] = None,
        project: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        self._init_vertex_credentials(credentials, location, project)
        self._vertex_config = self._load_vertex_config()

        # Initialize parent LiteLLMEmbedder with vertex_ai prefix
        # Don't pass api_key as Vertex AI uses credentials
        super().__init__(
            model_name=f"{self.PROVIDER}/{model_name}",
            api_key=None,
            dimensions=dimensions,
        )

    def _with_vertex_credentials(self, func, *args, **kwargs):
        """Execute a function with Vertex AI credentials injected.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the function
        """
        kwargs["vertex_project"] = self._vertex_config["project"]
        kwargs["vertex_location"] = self._vertex_config["location"]
        kwargs["vertex_credentials"] = self._vertex_config["vertex_credentials"]

        return func(*args, **kwargs)

    def generate(self, text: str, **kwargs) -> Embedding:
        """Generate embedding for a single text using Vertex AI.

        Args:
            text: The input text to embed.
            **kwargs: Additional parameters passed to litellm.embedding().

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            TypeError: If text is not a string.
        """
        return self._with_vertex_credentials(super().generate, text, **kwargs)

    async def a_generate(self, text: str, **kwargs) -> Embedding:
        """Async embedding for a single text using Vertex AI."""
        kwargs["vertex_project"] = self._vertex_config["project"]
        kwargs["vertex_location"] = self._vertex_config["location"]
        kwargs["vertex_credentials"] = self._vertex_config["vertex_credentials"]
        return await super().a_generate(text, **kwargs)

    def generate_batch(self, texts: List[str], **kwargs) -> List[Embedding]:
        """Generate embeddings for multiple texts using Vertex AI.

        Args:
            texts: List of input texts to embed.
            **kwargs: Additional parameters passed to litellm.embedding().

        Returns:
            A list of embedding vectors, one for each input text.

        Raises:
            TypeError: If texts is not a list or contains non-string elements.
        """
        return self._with_vertex_credentials(super().generate_batch, texts, **kwargs)

    def get_config_info(self) -> dict:
        """
        Get current Vertex AI configuration (useful for debugging).

        Returns:
            dict: Configuration details including project, location, and credentials source
        """
        return {
            "provider": self.PROVIDER,
            "model": self.model_name,
            "project": self._vertex_config["project"],
            "location": self._vertex_config["location"],
            "credentials_source": self._vertex_config.get("credentials_source", "unknown"),
        }
