from typing import Optional

from rhesis.sdk.models import HuggingFaceLLM


class Dolphin3(HuggingFaceLLM):
    """
    tag: working
    A specific implementation for the Dolphin3 model.
    This class extends HuggingFaceLLM to provide model-specific arguments.
    """

    def __init__(
        self,
        model_name: str = "dphn/Dolphin3.0-Llama3.2-3B",
        auto_loading: bool = False,
        generate_kwargs: Optional[dict] = None,
        gpu_only: bool = False,
        load_kwargs: Optional[dict] = None,
        custom_results_dir: Optional[str] = None,
    ):
        super().__init__(
            model_name=model_name,
            auto_loading=auto_loading,
            generate_kwargs=generate_kwargs,
            gpu_only=gpu_only,
            load_kwargs=load_kwargs,
            custom_results_dir=custom_results_dir,
        )
