from typing import Any, List, Optional

from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.llms import LLM

from rhesis.sdk.async_utils import run_sync
from rhesis.sdk.models.base import BaseLLM


class CustomLLM(LLM):
    """Langchain LLM wrapper around a Rhesis BaseLLM.

    Async-first: ``_acall`` holds the real implementation (delegates to
    ``rhesis_model.a_generate``).  The sync ``_call`` bridges through
    ``run_sync``.
    """

    n: int = 0
    rhesis_model: BaseLLM

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        return run_sync(self._acall(prompt, stop=stop, run_manager=None, **kwargs))

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        response = await self.rhesis_model.a_generate(prompt)
        return str(response)

    @property
    def _llm_type(self) -> str:
        return "custom"
