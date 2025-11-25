from typing import Optional

from rhesis.sdk.models.providers.huggingface import HuggingFaceLLM


class DeepHermes3(HuggingFaceLLM):
    """
    tag: working
    A specific implementation for the Deep Hermes model.
    This class extends HuggingFaceLLM to provide model-specific arguments.
    """

    def __init__(
        self,
        model_name: str = "NousResearch/DeepHermes-3-Llama-3-3B-Preview",
        auto_loading: bool = False,
        generate_kwargs: Optional[dict] = None,
        gpu_only: bool = False,
        load_kwargs: Optional[dict] = None,
        custom_results_dir: Optional[str] = None,
    ):
        if generate_kwargs is None:
            generate_kwargs = {
                "max_new_tokens": 4096,
                "repetition_penalty": 1.1,
                "temperature": 0.8,
                "do_sample": True,
            }
        super().__init__(
            model_name=model_name,
            auto_loading=auto_loading,
            generate_kwargs=generate_kwargs,
            gpu_only=gpu_only,
            load_kwargs=load_kwargs,
            custom_results_dir=custom_results_dir,
        )
