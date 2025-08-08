from typing import Optional, Dict, Any

from rhesis.polyphemus.benchmarking.models import HuggingfaceModel
from rhesis.polyphemus.benchmarking.models.abstract_model import Invocation


class DeepHermes3(HuggingfaceModel):
    """
    tag: working
    A specific implementation for the Deep Hermes model.
    This class extends HuggingfaceModel to provide model-specific arguments.
    """

    def get_recommended_request(self, prompt: str, system_prompt: Optional[str], additional_params: Optional[Dict[str, Any]]) -> Invocation:
        # Enable model to think deeply before responding
        thinking_prompt = "You are a deep thinking AI, you may use extremely long chains of thought to deeply consider the problem and deliberate with yourself via systematic reasoning processes to help come to a correct solution prior to answering. You should enclose your thoughts and internal monologue inside <think> </think> tags, and then provide your solution or response to the problem."
        if system_prompt is None or system_prompt == "":
            system_prompt = thinking_prompt
        else:
            system_prompt = thinking_prompt + "\n" + system_prompt

        additional_params.setdefault("max_new_tokens", 4096) # should probably be even higher due to reasoning
        additional_params.setdefault("repetition_penalty", 1.1)
        additional_params.setdefault("temperature", 0.8)
        additional_params.setdefault("do_sample", True)

        return super().get_recommended_request(prompt=prompt, system_prompt=system_prompt, additional_params=additional_params)