from typing import TYPE_CHECKING, Any, ClassVar, Dict, Literal, Optional, Union

from pydantic import model_validator

from rhesis.sdk.clients import APIClient, Endpoints, Methods

if TYPE_CHECKING:
    from rhesis.sdk.models.base import BaseEmbedder, BaseLLM
from rhesis.sdk.entities.base_collection import BaseCollection
from rhesis.sdk.entities.base_entity import BaseEntity

ENDPOINT = Endpoints.MODELS


class Model(BaseEntity):
    """
    Model entity for interacting with the Rhesis API.

    Models represent AI model configurations (LLMs or embeddings) that can be
    used for generation, evaluation, embedding, and other AI-powered tasks.
    Each model configuration includes the provider, model name, and API key.

    Examples:
        Create a new LLM model:
        >>> model = Model(
        ...     name="GPT-4 Production",
        ...     provider="openai",
        ...     model_name="gpt-4",
        ...     key="sk-..."
        ... )
        >>> model.push()

        Create an embedding model:
        >>> model = Model(
        ...     name="OpenAI Embeddings",
        ...     provider="openai",
        ...     model_name="text-embedding-3-small",
        ...     model_type="embedding",
        ...     key="sk-..."
        ... )
        >>> model.push()

        Load an existing model:
        >>> model = Models.pull(name="GPT-4 Production")
        >>> print(model.model_name)

        List all models:
        >>> models = Models.all()
        >>> for m in models:
        ...     print(m.name, m.model_type, m.model_name)

    Supported providers:
        - openai, anthropic, gemini, mistral, cohere, groq
        - vertex_ai, together_ai, replicate, perplexity
        - ollama, vllm (for self-hosted models)
    """

    endpoint: ClassVar[Endpoints] = ENDPOINT

    # Core identification
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

    # Model configuration
    provider: Optional[str] = None  # Provider name (e.g., "openai", "anthropic")
    model_name: Optional[str] = None
    model_type: Optional[Literal["llm", "embedding"]] = "llm"
    key: Optional[str] = None  # Provider API key

    # Relationships (resolved automatically from provider)
    provider_type_id: Optional[str] = None
    status_id: Optional[str] = None

    @model_validator(mode="after")
    def _set_default_description(self) -> "Model":
        """Set default description based on provider if not provided."""
        if self.description is None and self.provider:
            self.description = f"{self.provider.title()} model connection"
        return self

    def _resolve_provider_type_id(self) -> Optional[str]:
        """Resolve provider name to provider_type_id via API lookup."""
        if not self.provider:
            return self.provider_type_id

        client = APIClient()
        # Query type_lookups for provider with matching type_value and type_name
        filter_query = (
            f"type_name eq 'ProviderType' and tolower(type_value) eq '{self.provider.lower()}'"
        )
        response = client.send_request(
            endpoint=Endpoints.TYPE_LOOKUPS,
            method=Methods.GET,
            params={"$filter": filter_query},
        )

        if response and len(response) > 0:
            return response[0].get("id")

        available_providers = Models.list_providers()
        raise ValueError(
            f"Unsupported provider '{self.provider}'. "
            f"Supported providers: {', '.join(available_providers)}"
        )

    def push(self) -> Optional[Dict[str, Any]]:
        """Save the model to the platform.

        If a provider name is set, it will be automatically resolved to
        the provider_type_id before saving. The icon is automatically set
        based on the provider.
        """
        # Validate provider is set
        if not self.provider and not self.provider_type_id:
            available_providers = Models.list_providers()
            raise ValueError(
                f"Provider is required. Supported providers: {', '.join(available_providers)}"
            )

        # Resolve provider name to provider_type_id if needed
        if self.provider and not self.provider_type_id:
            self.provider_type_id = self._resolve_provider_type_id()

        # Build data dict and add icon (not exposed as a user field)
        data = self.model_dump(mode="json")

        # Set icon to provider value (same as frontend does)
        if self.provider:
            data["icon"] = self.provider.lower()

        if "id" in data and data["id"] is not None:
            response = self._update(data["id"], data)
        else:
            response = self._create(data)
            self.id = response["id"]

        return response

    def set_default_generation(self) -> None:
        """Set this model as the default for test generation.

        This updates the current user's settings to use this model
        when generating new test cases.

        Raises:
            ValueError: If model ID is not set (model must be saved first)

        Example:
            >>> model = Models.pull(name="GPT-4 Production")
            >>> model.set_default_generation()
        """
        if not self.id:
            raise ValueError("Model must be saved before setting as default. Call push() first.")

        client = APIClient()
        client.send_request(
            endpoint=Endpoints.USERS,
            method=Methods.PATCH,
            url_params="settings",
            data={"models": {"generation": {"model_id": self.id}}},
        )

    def set_default_evaluation(self) -> None:
        """Set this model as the default for evaluation (LLM as Judge).

        This updates the current user's settings to use this model
        when running metrics and evaluations.

        Raises:
            ValueError: If model ID is not set (model must be saved first)

        Example:
            >>> model = Models.pull(name="GPT-4 Production")
            >>> model.set_default_evaluation()
        """
        if not self.id:
            raise ValueError("Model must be saved before setting as default. Call push() first.")

        client = APIClient()
        client.send_request(
            endpoint=Endpoints.USERS,
            method=Methods.PATCH,
            url_params="settings",
            data={"models": {"evaluation": {"model_id": self.id}}},
        )

    def set_default_embedding(self) -> None:
        """Set this model as the default for embedding generation.

        This updates the current user's settings to use this model
        when generating embeddings for semantic search and similarity.

        Raises:
            ValueError: If model ID is not set (model must be saved first)

        Example:
            >>> model = Models.pull(name="OpenAI Embeddings")
            >>> model.set_default_embedding()
        """
        if not self.id:
            raise ValueError("Model must be saved before setting as default. Call push() first.")

        client = APIClient()
        client.send_request(
            endpoint=Endpoints.USERS,
            method=Methods.PATCH,
            url_params="settings",
            data={"models": {"embedding": {"model_id": self.id}}},
        )

    def get_model_instance(
        self,
    ) -> "Union[BaseLLM, BaseEmbedder]":
        """Create a model instance configured with this model's settings.

        Returns a ready-to-use LLM or embedder client based on the
        model_type. Uses the provider, model name, and API key from
        this entity.

        Returns:
            BaseLLM or BaseEmbedder: Ready-to-use model instance

        Raises:
            ValueError: If provider or model_name is not set

        Example:
            >>> model = Models.pull(name="GPT-4 Production")
            >>> llm = model.get_model_instance()
            >>> response = llm.generate("Hello, how are you?")

            >>> model = Models.pull(name="OpenAI Embeddings")
            >>> embedder = model.get_model_instance()
            >>> vector = embedder.generate("Hello, world!")
        """
        if not self.provider:
            raise ValueError("Provider is required to create a model instance")
        if not self.model_name:
            raise ValueError("Model name is required to create a model instance")

        if self.model_type == "embedding":
            from rhesis.sdk.models.factory import get_embedder

            return get_embedder(
                provider=self.provider,
                model_name=self.model_name,
                api_key=self.key,
            )

        from rhesis.sdk.models.factory import get_model

        return get_model(
            provider=self.provider,
            model_name=self.model_name,
            api_key=self.key,
        )


class Models(BaseCollection):
    """Collection class for Model entities."""

    endpoint = ENDPOINT
    entity_class = Model

    @classmethod
    def list_providers(cls) -> list[str]:
        """List available provider names.

        Returns:
            List of provider names that can be used when creating models.

        Example:
            >>> providers = Models.list_providers()
            >>> print(providers)
            ['openai', 'anthropic', 'gemini', 'mistral', ...]
        """
        client = APIClient()
        response = client.send_request(
            endpoint=Endpoints.TYPE_LOOKUPS,
            method=Methods.GET,
            params={"$filter": "type_name eq 'ProviderType'", "limit": 100},
        )

        if response:
            return [item.get("type_value") for item in response if item.get("type_value")]
        return []
