from rhesis.sdk.models import HuggingFaceLLM


class Dolphin3(HuggingFaceLLM):
    """
    tag: working
    A specific implementation for the Dolphin3 model.
    This class extends HuggingFaceLLM to provide model-specific arguments.
    """

    def __init__(self, model_name: str = "dphn/Dolphin3.0-Llama3.2-3B"):
        super().__init__(
            model_name=model_name,
            auto_loading=False,
        )
