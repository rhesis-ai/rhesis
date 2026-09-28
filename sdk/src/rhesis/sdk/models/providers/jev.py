import asyncio
import os
from typing import Any, Dict, Optional

import requests

from rhesis.sdk.config import DEFAULT_LLM_TIMEOUT
from rhesis.sdk.models.base import BaseDecisionModel
from rhesis.sdk.models.defaults import DEFAULT_DECISION_MODELS, model_name_from_id

DEFAULT_MODEL = DEFAULT_DECISION_MODELS["jev"]
DEFAULT_MODEL_NAME = model_name_from_id(DEFAULT_MODEL)
DEFAULT_API_BASE = "https://api.typesafe.ai"
DECISIONS_PATH = "/v1/systemone"


class JevDecisionModel(BaseDecisionModel):
    """TypeSafe AI's Jev, called through its System One API."""

    PROVIDER = "jev"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ):
        """
        Args:
            model_name: Jev model, e.g. "jev-latest" or "jev-1.13.0".
            api_key: TypeSafe API key. Falls back to TYPESAFE_API_KEY.
            api_base: API base URL. Falls back to TYPESAFE_API_BASE, then
                https://api.typesafe.ai. A LiteLLM proxy works too:
                ``https://<proxy>/typesafe`` with a LiteLLM virtual key.

        Raises:
            ValueError: If no API key is set.
        """
        self.api_key = api_key or os.getenv("TYPESAFE_API_KEY")
        if not self.api_key:
            raise ValueError("TYPESAFE_API_KEY is not set")
        self.api_base = (api_base or os.getenv("TYPESAFE_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        super().__init__(model_name or DEFAULT_MODEL_NAME, **kwargs)

    async def a_decide(self, state: Any, questions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        payload = {"model": self.model_name, "state": state, "questions": questions}
        response = await asyncio.to_thread(
            requests.post,
            f"{self.api_base}{DECISIONS_PATH}",
            headers=self.headers,
            json=payload,
            timeout=DEFAULT_LLM_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        self._emit_usage(body.get("usage"))
        return body["answers"]
