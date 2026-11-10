"""
Service for testing model connections.

This module provides functionality to test connections to various LLM and embedding
model providers before saving them to the database.
"""

import logging
from typing import Literal

import anyio

from rhesis.backend.app.utils.model_credentials import (
    credential_requirement,
    has_own_credentials,
    tenant_model_kwargs,
)
from rhesis.backend.app.utils.ssrf_http_client import (
    BLOCKED_TARGET_MESSAGE,
    SSRFError,
    validate_outbound_url,
)

logger = logging.getLogger(__name__)


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
    async def test_connection(
        provider: str,
        model_name: str,
        api_key: str,
        endpoint: str | None = None,
        model_type: Literal["language", "embedding", "decision"] = "language",
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
            model_type: Type of model - "language", "embedding" or "decision"

        Returns:
            ModelConnectionTestResult: Result of the connection test
        """
        try:
            logger.info(
                f"Testing connection for provider: {provider}, "
                f"model: {model_name}, type: {model_type}"
            )

            # Special handling for Rhesis system models (rhesis and polyphemus providers)
            if provider in ("rhesis", "polyphemus") and not api_key:
                # Protected/system model - uses backend infrastructure
                logger.info(
                    "%s system model detected - skipping connection test "
                    "(uses backend infrastructure)",
                    provider,
                )
                provider_label = provider.capitalize()
                return ModelConnectionTestResult(
                    success=True,
                    message=(
                        f"{provider_label}-hosted model is ready to use. "
                        f"This model uses {provider_label} infrastructure."
                    ),
                    provider=provider,
                    model_name=model_name,
                )

            if provider == "rhesis" and api_key:
                from rhesis.backend.app.config.settings import get_model_settings
                from rhesis.sdk.models.defaults import parse_model_id

                # When the system default is not Rhesis, skip strict validation.
                # RHESIS_API_KEY is only required when Rhesis is the default provider.
                default_generation_model = get_model_settings().generation_model
                default_provider, _ = parse_model_id(default_generation_model)
                if default_provider and default_provider != provider:
                    logger.info(
                        "Rhesis model detected but system default is %s - skipping connection test",
                        default_generation_model,
                    )
                    return ModelConnectionTestResult(
                        success=True,
                        message=(
                            "Rhesis model configured. The system is currently "
                            "using a different default provider."
                        ),
                        provider=provider,
                        model_name=model_name,
                    )

            if not has_own_credentials(provider, api_key, endpoint):
                # The provider would fall back to this server's own credentials, so a
                # success here would say nothing about the user's configuration.
                return ModelConnectionTestResult(
                    success=False,
                    message=f"Configuration error: {provider} needs "
                    f"{credential_requirement(provider)}.",
                    provider=provider,
                    model_name=model_name,
                )

            if endpoint and endpoint.strip():
                try:
                    await anyio.to_thread.run_sync(
                        lambda: validate_outbound_url(endpoint.strip(), allow_unresolved=True)
                    )
                except SSRFError:
                    return ModelConnectionTestResult(
                        success=False,
                        message=f"Endpoint URL rejected: {BLOCKED_TARGET_MESSAGE}.",
                        provider=provider,
                        model_name=model_name,
                    )

            if model_type == "language":
                return await ModelConnectionService._test_llm_connection(
                    provider, model_name, api_key, endpoint
                )
            elif model_type == "embedding":
                return ModelConnectionService._test_embedding_connection(
                    provider, model_name, api_key, endpoint
                )
            elif model_type == "decision":
                return await ModelConnectionService._test_decision_connection(
                    provider, model_name, api_key, endpoint
                )
            else:
                return ModelConnectionTestResult(
                    success=False,
                    message=(
                        f"Invalid model type: {model_type}. "
                        "Must be 'language', 'embedding' or 'decision'"
                    ),
                    provider=provider,
                    model_name=model_name,
                )

        except Exception:
            # `message` is handed to the client in a 200 body, where no masking
            # layer can see it -- so a failure of ours gets a fixed string and
            # the reason goes to the log instead.
            logger.exception("Unexpected error testing model connection")
            return ModelConnectionTestResult(
                success=False,
                message=(
                    "The connection test could not be completed due to an "
                    "internal error. Please try again."
                ),
                provider=provider,
                model_name=model_name,
            )

    @staticmethod
    async def _test_llm_connection(
        provider: str, model_name: str, api_key: str, endpoint: str | None = None
    ) -> ModelConnectionTestResult:
        """Test a language model connection."""
        try:
            from rhesis.backend.app.utils.usage_tracking import stamp_usage_provenance
            from rhesis.sdk.models.factory import get_model

            # Try to create the model instance
            try:
                # Never metered: this runs a real generation against
                # credentials the user just supplied to be tested. Those
                # tokens are billed to them by their provider, so charging
                # them to their Rhesis quota as well would be double billing.
                model = stamp_usage_provenance(
                    get_model(
                        provider=provider,
                        model_name=model_name,
                        **tenant_model_kwargs(provider, api_key, endpoint),
                    ),
                    metered=False,
                )
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
                _ = await model.a_generate(prompt=test_prompt)

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
                # The provider's own text goes to the user, not to our logs: it
                # can quote the API key they just typed ("Incorrect API key
                # provided: sk-...").
                logger.warning(
                    "Language model generation test failed for %s: %s",
                    provider,
                    type(e).__name__,
                )
                return ModelConnectionTestResult(
                    success=False,
                    message=str(e),
                    provider=provider,
                    model_name=model_name,
                )

        except Exception:
            logger.exception("Unexpected error testing language model connection")
            return ModelConnectionTestResult(
                success=False,
                message=(
                    "The connection test could not be completed due to an "
                    "internal error. Please try again."
                ),
                provider=provider,
                model_name=model_name,
            )

    @staticmethod
    async def _test_decision_connection(
        provider: str, model_name: str, api_key: str, endpoint: str | None = None
    ) -> ModelConnectionTestResult:
        """Test a decision model (e.g. Jev) by asking it one choice question."""
        from rhesis.backend.app.utils.usage_tracking import stamp_usage_provenance
        from rhesis.sdk.models.factory import get_model

        def result(success: bool, message: str) -> ModelConnectionTestResult:
            return ModelConnectionTestResult(
                success=success, message=message, provider=provider, model_name=model_name
            )

        try:
            # Never metered, as for language models: the user's own key pays.
            model = stamp_usage_provenance(
                get_model(
                    provider,
                    model_name,
                    model_type="decision",
                    **tenant_model_kwargs(provider, api_key, endpoint),
                ),
                metered=False,
            )
        except ValueError as e:
            return result(False, f"Configuration error: {e}")

        try:
            await model.a_decide(
                "Connection test.",
                {
                    "ok": {
                        "type": "choice",
                        "instructions": "Is this a connection test?",
                        "criteria": {"yes": "It is a connection test", "no": "It is not"},
                    }
                },
            )
        except Exception as e:
            # The provider's text goes to the user, not our logs: it can quote their key.
            logger.warning("Decision model test failed for %s: %s", provider, type(e).__name__)
            return result(False, str(e))
        return result(True, f"Successfully connected to {provider}. Model is responding correctly.")

    @staticmethod
    def _test_embedding_connection(
        provider: str, model_name: str, api_key: str, endpoint: str | None = None
    ) -> ModelConnectionTestResult:
        """Test an embedding model connection."""
        try:
            from rhesis.sdk.models.factory import get_model

            # Try to create the embedder instance
            try:
                embedder = get_model(
                    provider=provider,
                    model_name=model_name,
                    model_type="embedding",
                    **tenant_model_kwargs(provider, api_key, endpoint),
                )
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
                # Provider text is for the user only -- see the language-model
                # branch above.
                logger.warning(
                    "Embedding model generation test failed for %s: %s",
                    provider,
                    type(e).__name__,
                )
                return ModelConnectionTestResult(
                    success=False,
                    message=str(e),
                    provider=provider,
                    model_name=model_name,
                )

        except Exception:
            logger.exception("Unexpected error testing embedding connection")
            return ModelConnectionTestResult(
                success=False,
                message=(
                    "The connection test could not be completed due to an "
                    "internal error. Please try again."
                ),
                provider=provider,
                model_name=model_name,
            )
