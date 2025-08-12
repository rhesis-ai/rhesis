import time
from typing import Optional, Dict, Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .abstract_model import Model, ModelProvider, Invocation, ModelResponse


class HuggingfaceModel(Model):
    """
    A standard implementation of a model available on Hugging Face's model hub.
    This class provides a basic structure for loading and using models from Hugging Face.
    It can be extended to include specific models or configurations as needed.
    A complete implementation may be needed for unusual models or configurations.
    """

    def __init__(self, name: str, location: str):
        """
        Initialize the model with the given name and location.
        Args:
            name: The name of the model for identification in logs and responses
            location: The location of the model on Hugging Face's model hub
        """
        super().__init__()

        # information for logging and response
        self.name = name
        self.location = location
        self.provider = ModelProvider.HUGGINGFACE
        self.model = None
        self.device = None
        self.tokenizer = None

    def load_model(self):
        """
        Load the model and tokenizer from the specified location.
        """
        if self.model is not None:
            print(f"Model {self.name} is already loaded. Will be reloaded.")
        if self.tokenizer is not None:
            print(f"Tokenizer for {self.name} is already loaded. Will be reloaded.")

        self.model = AutoModelForCausalLM.from_pretrained(
            self.location,
        )
        # check for memory size
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.location,
        )

    # noinspection PyBroadException
    def unload_model(self):
        """
        Aggressively unload the model and tokenizer to free up GPU/CPU memory.
        This handles edge cases such as partial allocations and hanging references.
        """
        import gc
        import torch

        # Unload model
        try:
            if self.model is not None:
                try:
                    self.model.cpu()
                except Exception:
                    pass
                try:
                    # Clear state_dict if available
                    if hasattr(self.model, "state_dict"):
                        sd = self.model.state_dict()
                        for k in list(sd.keys()):
                            sd.pop(k)
                        del sd
                except Exception:
                    pass
                del self.model
                self.model = None
        except Exception:
            pass

        # Unload tokenizer
        try:
            if self.tokenizer is not None:
                try:
                    if hasattr(self.tokenizer, 'backend_tokenizer'):
                        self.tokenizer.backend_tokenizer = None
                except Exception:
                    pass
                del self.tokenizer
                self.tokenizer = None
        except Exception:
            pass

        # Force cleanup
        torch.cuda.empty_cache()
        gc.collect()
        torch.cuda.empty_cache()

    def generate_response(self, invocation: Invocation) -> ModelResponse:
        """
        Generate a response from the model for the given invocation.
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model and tokenizer must be loaded before generating a response.")

        start = time.time()

        messages = [
            {"role": "system", "content": invocation.system_prompt},
            {"role": "user", "content": invocation.prompt}
        ] if invocation.system_prompt else [
            {"role": "user", "content": invocation.prompt},
        ]
        inputs = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_dict=True,
                                                    return_tensors="pt").to(self.device)

        output_ids = self.model.generate(
            **inputs,
            pad_token_id=self.tokenizer.eos_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            **invocation.additional_params,
        )

        completion = self.tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1]:],  # only take the newly generated content
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True
        ).strip()

        num_tokens = len(output_ids[0])
        self.tokens_used += num_tokens

        end = time.time()

        return ModelResponse(
            content=completion,
            model_name=self.name,
            model_location=self.location,
            provider=self.provider,
            request=invocation,
            tokens_used=num_tokens,
            response_time=end - start,
            error=None
        )

    def get_recommended_request(self, prompt: str, system_prompt: Optional[str], additional_params: Optional[Dict[str, Any]]) -> Invocation:
        """
        Generate a recommended request for the given invocation.
        """
        additional_params.setdefault("max_new_tokens", 512)
        return Invocation(prompt=prompt, system_prompt=system_prompt, additional_params=additional_params)
