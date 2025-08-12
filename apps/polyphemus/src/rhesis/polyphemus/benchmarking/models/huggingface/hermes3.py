from typing import Optional, Dict, Any

from rhesis.polyphemus.benchmarking.models import HuggingfaceModel
from rhesis.polyphemus.benchmarking.models.abstract_model import Invocation


class Hermes3(HuggingfaceModel):
    """
    tag: working
    A specific implementation for the Hermes3 model.
    This class extends HuggingfaceModel to provide model-specific arguments.
    """

    def get_recommended_request(self, prompt: str, system_prompt: Optional[str], additional_params: Optional[Dict[str, Any]]) -> Invocation:
        additional_params.setdefault("repetition_penalty", 1.1)
        additional_params.setdefault("temperature", 0.8)
        additional_params.setdefault("do_sample", True)

        return super().get_recommended_request(prompt=prompt, system_prompt=system_prompt, additional_params=additional_params)
