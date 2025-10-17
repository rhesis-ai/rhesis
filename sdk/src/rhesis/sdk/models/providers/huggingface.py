import gc
import json
from typing import Optional

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:
    raise ImportError(
        "HuggingFace dependencies are not installed.\n"
        "Please install them with:\n"
        "  pip install rhesis-sdk[huggingface]\n"
        "or:\n"
        "  uv sync --extra huggingface"
    )

from pydantic import BaseModel

from rhesis.sdk.errors import (
    HUGGINGFACE_MODEL_NOT_LOADED,
    MODEL_RELOAD_WARNING,
    NO_MODEL_NAME_PROVIDED,
    WARNING_TOKENIZER_ALREADY_LOADED_RELOAD,
)
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.utils import validate_llm_response


class HuggingFaceLLM(BaseLLM):
    """
    A standard implementation of a model available on Hugging Face's model hub.
    This class provides a basic structure for loading and using models from Hugging Face.
    It can be extended to include specific models or configurations as needed.
    A complete implementation may be needed for unusual models or configurations.
    Example usage:
        >>> llm = HugginFaceLLM("crumb/nano-mistral")
        >>> result = llm.generate("Tell me a joke.")
        >>> print(result)
    """

    def __init__(
        self, model_name: str, auto_loading: bool = True, default_kwargs: Optional[dict] = None
    ):
        """
        Initialize the model with the given name and location.
        Args:
            model_name: The location to pull the model from
            auto_loading: Whether to automatically load the model on initialization.
             If turned off, manual loading is needed. Allows lazy loading.
        """
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)

        self.model_name = model_name
        self.default_kwargs = default_kwargs

        self.model = None
        self.tokenizer = None
        self.device = None

        if auto_loading:
            (self.model, self.tokenizer, self.device) = self.load_model()

    def __del__(self):
        """
        If the model or tokenizer is loaded, unload them to free up resources.
        Unloading manually is cleaner, but this is a fallback.
        """
        if self.model is not None or self.tokenizer is not None:
            self.unload_model()

    def load_model(self):
        """
        Load the model and tokenizer from the specified location.
        """
        if self.model is not None:
            print(MODEL_RELOAD_WARNING.format(self.model_name))
        if self.tokenizer is not None:
            print(WARNING_TOKENIZER_ALREADY_LOADED_RELOAD.format(self.model_name))

        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)

        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
        )

        return model, tokenizer, device

    def unload_model(self):
        """
        Aggressively unload the model and tokenizer to free up GPU/CPU memory.
        This handles edge cases such as partial allocations and hanging references.
        """
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
                    if hasattr(self.tokenizer, "backend_tokenizer"):
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

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[BaseModel] = None,
        **kwargs,
    ) -> str:
        """
        Generate a response from the model.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional Pydantic BaseModel for structured output
            **kwargs: Additional generation parameters

        Returns:
            str if no schema provided, dict if schema provided
        """

        # check model and tokenizer
        if self.model is None or self.tokenizer is None:
            raise RuntimeError(HUGGINGFACE_MODEL_NOT_LOADED)

        # format arguments
        if self.default_kwargs:
            kwargs = {**self.default_kwargs, **kwargs}

        # If schema is provided, augment the prompt to request JSON output
        if schema:
            json_schema = schema.model_json_schema()
            schema_instruction = (
                f"\n\nYou must respond with valid JSON matching this schema:\n"
                f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
                f"Only return the JSON object, nothing else. "
                f"Do not include explanations or markdown."
            )
            prompt = prompt + schema_instruction

        if hasattr(self.tokenizer, "chat_template") and self.tokenizer.chat_template is not None:
            messages = (
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
                if system_prompt
                else [
                    {"role": "user", "content": prompt},
                ]
            )
            inputs = self.tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, return_dict=True, return_tensors="pt"
            ).to(self.device)
        else:
            messages = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            inputs = self.tokenizer(messages, return_tensors="pt").to(self.device)

        # generate response
        output_ids = self.model.generate(
            **inputs,
            pad_token_id=self.tokenizer.eos_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            **kwargs,
        )

        completion = self.tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1] :],  # only take the newly generated content
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        ).strip()

        # If schema was provided, parse and validate the JSON response
        if schema:
            response_dict = json.loads(completion)
            validate_llm_response(response_dict, schema)
            return response_dict

        return completion
