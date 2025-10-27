"""
Service for testing model connections.

This module provides functionality to test connections to various LLM providers
before saving them to the database.
"""

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
        provider: str, model_name: str, api_key: str, endpoint: str | None = None
    ) -> ModelConnectionTestResult:
        """
        Test a model connection by attempting to initialize and use the model.

        This validates that:
        1. The provider is supported by the SDK
        2. The API key is valid
        3. The model can be initialized successfully
        4. A simple generation call works (for full validation)

        Args:
            provider: The provider name (e.g., "openai", "gemini", "ollama")
            model_name: The specific model name
            api_key: The API key for authentication
            endpoint: Optional endpoint URL for self-hosted providers

        Returns:
            ModelConnectionTestResult: Result of the connection test
        """
        try:
            from rhesis.sdk.models.factory import ModelConfig, get_model

            logger.info(f"Testing connection for provider: {provider}, model: {model_name}")

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
                logger.warning(f"Model configuration error: {str(e)}")
                return ModelConnectionTestResult(
                    success=False,
                    message=f"Configuration error: {str(e)}",
                    provider=provider,
                    model_name=model_name,
                )

            # Try a simple generation to verify the connection works
            try:
                test_prompt = "Say 'OK' if you can read this."
                response = model.generate(prompt=test_prompt)

                logger.info(f"Connection test successful for {provider}/{model_name}")
                return ModelConnectionTestResult(
                    success=True,
                    message=f"Successfully connected to {provider}. Model is responding correctly.",
                    provider=provider,
                    model_name=model_name,
                )
            except Exception as e:
                # API call failed - likely authentication or network issue
                logger.warning(f"Model generation test failed: {str(e)}")

                # Return the original error message from the provider
                # Different providers have different error formats, so we keep them as-is
                error_message = str(e)

                return ModelConnectionTestResult(
                    success=False,
                    message=error_message,
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
