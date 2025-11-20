import os

from rhesis.sdk.models.providers.litellm import LiteLLM

DEFAULT_MODEL_NAME = "gpt-4"


class OpenAILLM(LiteLLM):
    PROVIDER = "openai"

    def __init__(self, model_name=DEFAULT_MODEL_NAME, api_key=None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise ValueError("OPENAI_API_KEY is not set")
        super().__init__(self.PROVIDER + "/" + model_name, api_key=api_key)
