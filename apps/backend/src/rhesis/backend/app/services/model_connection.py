"""
Service for testing model connections.

This module provides functionality to test connections to various LLM and embedding
model providers before saving them to the database.
"""

from typing import Literal

from rhesis.backend.logging import logger


class ModelConnectionTestResult:
    """Result of a model connection test."""

    def __init__(self, success: bool, message: str, provider: str, model_name: str):
        self.success = success
        self.message = message
        self.provider = provider
        self.model_name = model_name


class ModelConnectionService:
    """Service for testing model connections."""

    @staticmethod
    def test_connection(
        provider: str,
        model_name: str,
        api_key: str,
        endpoint: str | None = None,
        model_type: Literal["llm", "embedding"] = "llm",
    ) -> ModelConnectionTestResult:
        """
        Test a model connection by attempting to initialize and use the model.

        This validates that:
        1. The provider is supported by the SDK
        2. The API key is valid
        3. The model can be initialized successfully
        4. A test call works (generation for LLMs, embedding for embedding models)

        Args:
            provider: The provider name (e.g., "openai", "gemini", "ollama")
            model_name: The specific model name
            api_key: The API key for authentication
            endpoint: Optional endpoint URL for self-hosted providers
            model_type: Type of model - "llm" or "embedding"

        Returns:
            ModelConnectionTestResult: Result of the connection test
        """
        try:
            logger.info(
                f"Testing connection for provider: {provider}, "
                f"model: {model_name}, type: {model_type}"
            )

            # Special handling for Rhesis system models (protected models with no API key)
            # These models use the backend's infrastructure and don't need testing
            if provider == "rhesis" and not api_key:
                logger.info(
                    "Rhesis system model detected - skipping connection test "
                    "(uses backend infrastructure)"
                )
                return ModelConnectionTestResult(
                    success=True,
                    message=(
                        "Rhesis-hosted model is ready to use. "
                        "This model uses Rhesis infrastructure and requires no API key."
                    ),
                    provider=provider,
                    model_name=model_name,
                )

            if model_type == "llm":
                return ModelConnectionService._test_llm_connection(
                    provider, model_name, api_key, endpoint
                )
            elif model_type == "embedding":
                return ModelConnectionService._test_embedding_connection(
                    provider, model_name, api_key, endpoint
                )
            else:
                return ModelConnectionTestResult(
                    success=False,
                    message=f"Invalid model type: {model_type}. Must be 'llm' or 'embedding'",
                    provider=provider,
                    model_name=model_name,
                )

        except Exception as e:
            logger.error(f"Unexpected error testing model connection: {str(e)}", exc_info=True)
            return ModelConnectionTestResult(
                success=False,
                message=f"Unexpected error: {str(e)}",
                provider=provider,
                model_name=model_name,
            )

    @staticmethod
    def _test_llm_connection(
        provider: str, model_name: str, api_key: str, endpoint: str | None = None
    ) -> ModelConnectionTestResult:
        """Test a language model connection."""
        try:
            from rhesis.sdk.models.factory import ModelConfig, get_model

            # Build extra params for providers that need them
            extra_params = {}
            if endpoint:
                extra_params["base_url"] = endpoint

            # Create model config
            config = ModelConfig(
                provider=provider,
                model_name=model_name,
                api_key=api_key,
                extra_params=extra_params,
            )

            # Try to create the model instance
            try:
                model = get_model(config=config)
            except ValueError as e:
                # Provider not supported or invalid configuration
                logger.warning(f"Language model configuration error: {str(e)}")
                return ModelConnectionTestResult(
                    success=False,
                    message=f"Configuration error: {str(e)}",
                    provider=provider,
                    model_name=model_name,
                )

            # Try a simple generation to verify the connection works
            try:
                test_prompt = "Say 'OK' if you can read this."
                _ = model.generate(prompt=test_prompt)

                logger.info(
                    f"Language model connection test successful for {provider}/{model_name}"
                )
                return ModelConnectionTestResult(
                    success=True,
                    message=f"Successfully connected to {provider}. Model is responding correctly.",
                    provider=provider,
                    model_name=model_name,
                )
            except Exception as e:
                # API call failed - likely authentication or network issue
                logger.warning(f"Language model generation test failed: {str(e)}")
                return ModelConnectionTestResult(
                    success=False,
                    message=str(e),
                    provider=provider,
                    model_name=model_name,
                )

        except Exception as e:
            logger.error(
                f"Unexpected error testing language model connection: {str(e)}", exc_info=True
            )
            return ModelConnectionTestResult(
                success=False,
                message=f"Unexpected error: {str(e)}",
                provider=provider,
                model_name=model_name,
            )

    @staticmethod
    def _test_embedding_connection(
        provider: str, model_name: str, api_key: str, endpoint: str | None = None
    ) -> ModelConnectionTestResult:
        """Test an embedding model connection."""
        try:
            from rhesis.sdk.models.factory import EmbedderConfig, get_embedder

            # Build extra params for providers that need them
            extra_params = {}
            if endpoint:
                extra_params["base_url"] = endpoint

            # Create embedder config
            config = EmbedderConfig(
                provider=provider,
                model_name=model_name,
                api_key=api_key,
                extra_params=extra_params,
            )

            # Try to create the embedder instance
            try:
                embedder = get_embedder(config=config)
            except ValueError as e:
                # Provider not supported or invalid configuration
                logger.warning(f"Embedding model configuration error: {str(e)}")
                return ModelConnectionTestResult(
                    success=False,
                    message=f"Configuration error: {str(e)}",
                    provider=provider,
                    model_name=model_name,
                )

            # Try a simple embedding generation to verify the connection works
            try:
                test_text = "Test embedding generation"
                embedding = embedder.generate(text=test_text)

                # Verify embedding is valid (should be a list/tuple of numbers)
                if not isinstance(embedding, (list, tuple)) or len(embedding) == 0:
                    raise ValueError("Invalid embedding response: expected non-empty vector")

                logger.info(
                    f"Embedding connection test successful for {provider}/{model_name}, "
                    f"vector size: {len(embedding)}"
                )
                return ModelConnectionTestResult(
                    success=True,
                    message=(
                        f"Successfully connected to {provider}. "
                        f"Embedding model is responding correctly (vector size: {len(embedding)})."
                    ),
                    provider=provider,
                    model_name=model_name,
                )
            except Exception as e:
                # API call failed - likely authentication or network issue
                logger.warning(f"Embedding model generation test failed: {str(e)}")
                return ModelConnectionTestResult(
                    success=False,
                    message=str(e),
                    provider=provider,
                    model_name=model_name,
                )

        except Exception as e:
            logger.error(f"Unexpected error testing embedding connection: {str(e)}", exc_info=True)
            return ModelConnectionTestResult(
                success=False,
                message=f"Unexpected error: {str(e)}",
                provider=provider,
                model_name=model_name,
            )
