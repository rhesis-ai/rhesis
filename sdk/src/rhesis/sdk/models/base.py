import logging
from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    TypedDict,
    Union,
)

from rhesis.sdk.async_utils import run_sync
from rhesis.sdk.models.utils import llm_retry

if TYPE_CHECKING:
    from rhesis.sdk.entities.model import Model

logger = logging.getLogger(__name__)


class TokenUsage(TypedDict):
    """Token counts for one LLM call, normalized across providers.

    Field names follow the OpenAI Responses API ``usage`` object, which is
    also what OpenTelemetry's GenAI semantic conventions use
    (``gen_ai.usage.input_tokens`` / ``gen_ai.usage.output_tokens``).
    Providers report these under a dozen different spellings
    (``prompt_tokens``, ``prompt_token_count``, ``promptTokenCount``, ...);
    :func:`_normalize_usage` maps all of them onto these three keys so
    consumers never have to guess which dialect a provider speaks.
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int


UsageCallback = Callable[[TokenUsage], None]

#: Signature of the process-wide sink registered via
#: :func:`set_default_usage_callback`. Unlike the per-instance
#: :attr:`BaseLLM.on_usage`, it also receives the model that produced the
#: usage, because a host application deciding whether to bill for those
#: tokens needs to know which model (and therefore whose credentials) ran
#: the call. See :attr:`BaseLLM.usage_metered`.
DefaultUsageCallback = Callable[[TokenUsage, "BaseLLM"], None]

_default_usage_callback: Optional[DefaultUsageCallback] = None


def set_default_usage_callback(callback: Optional[DefaultUsageCallback]) -> None:
    """Register a process-wide sink invoked for *every* model's token usage.

    The point of this over per-instance ``on_usage`` is that it cannot be
    forgotten. A host application that meters tokens registers one sink at
    startup and every model built anywhere in the process reports to it,
    including models constructed by code that has never heard of usage
    accounting. Wiring a callback per construction site is the same bug
    waiting to happen once per site.

    Fires *in addition to* any instance ``on_usage``, not instead of it, so
    a caller that attaches its own listener to one model does not silently
    detach that model from the host's accounting.

    Pass ``None`` to uninstall (mainly useful in tests).
    """
    global _default_usage_callback
    _default_usage_callback = callback


def get_default_usage_callback() -> Optional[DefaultUsageCallback]:
    """Return the sink registered by :func:`set_default_usage_callback`."""
    return _default_usage_callback


def _normalize_usage(usage: Any) -> Optional[TokenUsage]:
    """Parse a provider's raw usage payload into a :class:`TokenUsage`.

    Returns ``None`` when there is nothing worth reporting (no payload, or
    a payload that yields zero total tokens), so callers can treat the
    result as a simple "emit or skip" decision.

    Delegates the actual key-name matching to
    :func:`~rhesis.sdk.telemetry.utils.token_extraction.extract_token_usage`,
    which already handles every provider dialect and is used by the
    LangChain tracing integration -- there is no reason for the accrual
    path to grow a second, thinner copy of that logic. Imported lazily
    because ``rhesis.sdk.telemetry`` builds the OTel tracer and exporter
    on package init, and this module is on the import path of every SDK
    user; the ``on_usage is None`` guard in the callers means the import
    only ever happens for callers that actually wired up accrual.
    """
    if not usage:
        return None

    from rhesis.sdk.telemetry.utils.token_extraction import extract_token_usage

    input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
    if not total_tokens:
        return None

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


# Type alias for embeddings
Embedding = List[float]


class BaseModel(ABC):
    """Common base class for all model types (language, embedding, future: image)."""

    PROVIDER: str = ""  # Subclasses should override this
    MODEL_TYPE: str = ""  # "language", "embedding", "image" - subclasses should override

    def __init__(self, model_name: str, *args, **kwargs):
        self.model_name = model_name

    def get_model_name(self) -> str:
        return f"{self.__class__.__name__}: {self.model_name}"

    def push(self, name: str, description: Optional[str] = None) -> "Model":
        """Save this model configuration to the Rhesis platform as a Model entity.

        Creates a Model entity with this model's provider, model name, and API key,
        then saves it to the platform.

        Args:
            name: Name for the saved model configuration (required)
            description: Optional description for the model

        Returns:
            Model: The created Model entity

        Raises:
            ValueError: If provider is not set on this model class

        Example:
            >>> model = get_model("openai/gpt-4", api_key="sk-...")
            >>> model_entity = model.push(name="My Production Model")
        """
        from rhesis.sdk.entities.model import Model

        provider = getattr(self, "PROVIDER", None)
        if not provider:
            raise ValueError(
                "Cannot push model: PROVIDER class variable is not set. "
                "This model implementation does not support push()."
            )

        # Extract model name (remove provider prefix if present)
        model_name = (
            self.model_name.split("/", 1)[-1]
            if self.model_name and "/" in self.model_name
            else self.model_name
        )

        # Get API key if available
        api_key = getattr(self, "api_key", None)

        # Determine model_type from MODEL_TYPE class variable ("language" or "embedding")
        model_type = getattr(self, "MODEL_TYPE", "language")

        model = Model(
            name=name,
            description=description,
            provider=provider,
            model_name=model_name,
            model_type=model_type,
            key=api_key,
        )
        model.push()
        return model


class BaseLLM(BaseModel):
    MODEL_TYPE = "language"

    # Class-level defaults so the usage machinery works even on a subclass
    # that never chains to ``BaseLLM.__init__`` -- ``HuggingFaceLLM`` does
    # exactly that, because its lazy ``auto_loading=False`` mode is
    # incompatible with the base constructor eagerly calling ``load_model``.
    # Without these, ``_emit_usage`` raises AttributeError on such a model
    # instead of reporting its tokens. Instance assignment below shadows them.
    on_usage: Optional[UsageCallback] = None
    usage_metered: Optional[bool] = None

    def __init__(
        self,
        model_name,
        *args,
        on_usage: Optional[UsageCallback] = None,
        **kwargs,
    ):
        # `on_usage` is consumed here (keyword-only, not absorbed into
        # `**kwargs`) so it never reaches `load_model(*args, **kwargs)` --
        # provider `load_model()` implementations take no such parameter and
        # would raise TypeError if it leaked through.
        super().__init__(model_name, *args, **kwargs)
        self.model = self.load_model(*args, **kwargs)
        self.a_generate = llm_retry(self.a_generate)

        # Optional callback invoked with a normalized :class:`TokenUsage` at
        # the point a provider parses usage out of its API response --
        # inline, in the same call, rather than stashed on a shared attribute
        # for an external caller to poll afterward. That side-channel-attribute
        # design was tried and dropped: concurrent calls against one instance
        # (agents, batch executors) would race on it, and wrapping the
        # instance to intercept generate()/a_generate() broke every
        # ``isinstance(model, BaseLLM)`` check elsewhere in the stack. A
        # constructor-supplied callback keeps the returned object a real
        # provider instance and each call's usage local to its own stack frame.
        self.on_usage = on_usage

        # Whose credentials paid for this model's calls, for the benefit of a
        # host application metering tokens. The SDK never sets or reads this
        # itself -- it cannot know, since the same provider class is billable
        # or not depending on where its API key came from. ``None`` means
        # nobody stamped it, which a host should treat as "built outside my
        # resolution path" rather than as a quiet "no".
        self.usage_metered: Optional[bool] = None

        # # Only wrap generate with sync retry if the subclass overrides it.
        # # The base generate() delegates to a_generate() which already has
        # # retry, so wrapping both would cause double retry.
        # if type(self).generate is not BaseLLM.generate:
        #     self.generate = llm_retry(self.generate)

    @abstractmethod
    def load_model(self, *args, **kwargs):
        """Loads a model

        Returns:
            A model object
        """
        pass

    def _emit_usage(self, usage: Optional[Dict[str, Any]]) -> None:
        """Report normalized token counts for one call to every usage listener.

        Providers call this at the exact point they parse ``usage`` out of a
        raw API response -- see ``PolyphemusLLM.generate`` and
        ``RhesisLLM.create_completion`` for call sites. The raw payload is
        run through :func:`_normalize_usage` first, so a provider that
        reports only ``prompt_tokens``/``completion_tokens`` (no
        ``total_tokens``) still accrues correctly instead of being silently
        dropped.
        """
        self._dispatch_usage(_normalize_usage(usage))

    def _emit_usage_batch(self, usages: Iterable[Optional[Dict[str, Any]]]) -> None:
        """Sum usage across a batch's items and report it once.

        One aggregate emission rather than one per item: listeners typically
        queue a durable write (see
        ``rhesis.backend.app.services.usage.dispatch_accrual``), and a batch
        of N prompts should cost one of those, not N. Items with no usage
        payload contribute nothing.
        """
        if self.on_usage is None and _default_usage_callback is None:
            return

        totals = TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)
        for usage in usages:
            normalized = _normalize_usage(usage)
            if normalized is None:
                continue
            for key in totals:
                totals[key] += normalized[key]  # type: ignore[literal-required]

        self._dispatch_usage(totals if totals["total_tokens"] else None)

    def _dispatch_usage(self, usage: Optional[TokenUsage]) -> None:
        """Hand *usage* to the instance callback and the process-wide sink.

        Both, not one or the other: ``on_usage`` belongs to whoever built
        this particular model, while the sink belongs to the application and
        is how it accounts for tokens it pays for. Letting an instance
        callback suppress the sink would mean any caller attaching a listener
        silently opts that model out of the host's accounting -- which is the
        class of silent omission the sink exists to prevent.
        """
        if usage is None:
            return
        if self.on_usage is not None:
            self._invoke_on_usage(usage)
        if _default_usage_callback is not None:
            self._invoke_default_usage(usage, _default_usage_callback)

    def _invoke_on_usage(self, usage: TokenUsage) -> None:
        """Call ``on_usage``, swallowing anything it raises.

        ``on_usage`` is caller-supplied, and a broken listener must never
        break the LLM call that produced the usage.
        """
        try:
            self.on_usage(usage)  # type: ignore[misc]
        except Exception:
            logger.warning("on_usage callback raised; usage not recorded", exc_info=True)

    def _invoke_default_usage(self, usage: TokenUsage, callback: DefaultUsageCallback) -> None:
        """Call the process-wide sink, swallowing anything it raises."""
        try:
            callback(usage, self)
        except Exception:
            logger.warning("default usage callback raised; usage not recorded", exc_info=True)

    def generate(self, *args, **kwargs) -> Union[str, Dict[str, Any]]:
        """Runs the model to output LLM response.

        Bridges to a_generate() via run_sync(), which auto-detects
        whether a running event loop exists.

        Returns:
            A string or dict (if schema provided).
        """
        return run_sync(self.a_generate(*args, **kwargs))

    async def a_generate(
        self, *args, stream: bool = False, **kwargs
    ) -> Union[str, Dict[str, Any], AsyncGenerator[str, None]]:
        """Async version of generate. Subclasses must override this.

        Args:
            stream: When True, return an async generator yielding token
                chunks instead of the full response.

        Returns:
            A string or dict (if schema provided), or an async generator
            of string chunks when ``stream=True``.

        Raises:
            NotImplementedError: If the subclass does not implement this.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement a_generate(). "
            "Override a_generate() to enable async support."
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream LLM response token-by-token.

        Yields delta content strings. Default implementation falls back
        to ``generate()`` and yields the full result as a single chunk.
        Providers should override this for true streaming.
        """
        result = self.generate(prompt=prompt, system_prompt=system_prompt, **kwargs)
        if isinstance(result, dict):
            import json

            yield json.dumps(result)
        else:
            yield result

    @abstractmethod
    def generate_batch(self, *args, **kwargs) -> List[Union[str, Dict[str, Any]]]:
        """Runs the model on multiple prompts to output LLM responses.

        Returns:
            A list of strings or dicts (if schema provided).
        """
        pass

    async def warmup(self) -> None:
        """Pre-warm any provider-specific resources before concurrent use.

        Called once sequentially before ``asyncio.gather`` so that expensive
        one-time operations (e.g. fetching OAuth tokens, loading credentials)
        happen upfront rather than being repeated by every concurrent coroutine.
        The default implementation is a no-op; providers override as needed.
        """

    def get_available_models(self) -> List[str]:
        raise NotImplementedError("Subclasses must implement this method")


class BaseEmbedder(BaseModel):
    """Base class for embedding models."""

    MODEL_TYPE = "embedding"

    def __init__(self, model_name: str, *args, **kwargs):
        super().__init__(model_name, *args, **kwargs)

    def generate(self, text: str, **kwargs) -> Embedding:
        """Generate embedding for a single text (bridges to ``a_generate``).

        Args:
            text: The input text to embed.
            **kwargs: Additional parameters (e.g., dimensions).

        Returns:
            A list of floats representing the embedding vector.
        """
        return run_sync(self.a_generate(text, **kwargs))

    async def a_generate(self, text: str, **kwargs) -> Embedding:
        """Async embedding for a single text. Subclasses must override."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement a_generate(). "
            "Override a_generate() to enable async support."
        )

    @abstractmethod
    def generate_batch(self, texts: List[str], **kwargs) -> List[Embedding]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed.
            **kwargs: Additional parameters (e.g., dimensions).

        Returns:
            A list of embedding vectors, one for each input text.
        """
        pass

    def get_available_models(self) -> List[str]:
        """Get the list of available embedding models for this provider.

        Subclasses should override this method to return provider-specific embedding models.

        Returns:
            List of embedding model names

        Raises:
            NotImplementedError: If the subclass doesn't implement this method
        """
        raise NotImplementedError("Subclasses must implement this method")
