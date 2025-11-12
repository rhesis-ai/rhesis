from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM


class DeepHermes3(HuggingFaceLLM):
    """
    tag: working
    A specific implementation for the Deep Hermes model.
    This class extends HuggingFaceLLM to provide model-specific arguments.
    """

    def __init__(self, model_name: str = "NousResearch/DeepHermes-3-Llama-3-3B-Preview"):
        super().__init__(
            model_name=model_name,
            auto_loading=False,
            default_kwargs={
                "max_new_tokens": 4096,
                "repetition_penalty": 1.1,
                "temperature": 0.8,
                "do_sample": True,
            },
        )
