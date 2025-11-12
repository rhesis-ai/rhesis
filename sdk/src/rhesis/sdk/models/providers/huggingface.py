import gc
import json
import time
from typing import Optional, Type

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
        self,
        model_name: str,
        auto_loading: bool = True,
        default_kwargs: Optional[dict] = None,
        gpu_only: bool = False,
    ):
        """
        Initialize the model with the given name and location.
        Args:
            model_name: The location to pull the model from
            auto_loading: Whether to automatically load the model on initialization.
             If turned off, manual loading is needed. Allows lazy loading.
            default_kwargs: Default kwargs to pass to generate()
            gpu_only: If True, restrict model to GPU only (no CPU/disk offloading).
             Will raise an error if model doesn't fit in available GPU memory.
        """
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)

        self.model_name = model_name
        self.default_kwargs = default_kwargs
        self.gpu_only = gpu_only

        self.model = None
        self.tokenizer = None
        self.device = None
        self.last_generation_metadata = None

        if auto_loading:
            self.load_model()

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

        Returns
        -------
        self
            Returns self for method chaining

        Raises
        ------
        RuntimeError
            If gpu_only=True but CUDA is not available or model doesn't fit on GPU
        """
        if self.model is not None:
            print(MODEL_RELOAD_WARNING.format(self.model_name))
        if self.tokenizer is not None:
            print(WARNING_TOKENIZER_ALREADY_LOADED_RELOAD.format(self.model_name))

        # Configure device_map based on gpu_only flag
        if self.gpu_only:
            if not torch.cuda.is_available():
                raise RuntimeError(
                    "gpu_only=True but CUDA is not available. "
                    "Cannot load model without GPU."
                )
            device_map = "cuda"
            print("Loading model with gpu_only=True (device_map='cuda')")
        else:
            device_map = "auto"

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map=device_map,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
        )

        # Get the device for input tensors
        # When using device_map="auto", the model may be split across devices
        # We need to send inputs to the device of the first layer
        if hasattr(self.model, "hf_device_map"):
            # Model is split across devices - get the device of the first module
            first_device = next(iter(self.model.hf_device_map.values()))
            self.device = torch.device(first_device)

            # If gpu_only, verify no layers were offloaded to CPU/disk
            if self.gpu_only:
                offloaded_devices = set(self.model.hf_device_map.values())
                non_gpu_devices = [d for d in offloaded_devices if not str(d).startswith("cuda")]
                if non_gpu_devices:
                    raise RuntimeError(
                        f"gpu_only=True but model has layers offloaded to: {non_gpu_devices}. "
                        f"The model is too large for available GPU memory."
                    )
        else:
            # Model is on a single device
            self.device = self.model.device

        return self

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

    def _get_model_memory_gb(self) -> float:
        """
        Get the model's memory footprint in GB.
        Works for both CPU and GPU execution.
        """
        if self.model is None:
            return 0.0

        try:
            # Get model parameter memory
            param_size = sum(p.numel() * p.element_size() for p in self.model.parameters())
            # Get model buffer memory (non-trainable)
            buffer_size = sum(b.numel() * b.element_size() for b in self.model.buffers())
            total_bytes = param_size + buffer_size
            return round(total_bytes / (1024**3), 3)  # Convert to GB
        except Exception:
            return 0.0

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
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
            )
        else:
            messages = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            inputs = self.tokenizer(messages, return_tensors="pt")

        # Move inputs to the model's device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Capture essential metrics
        input_tokens = inputs["input_ids"].shape[1]
        model_memory_gb = self._get_model_memory_gb()
        start_time = time.time()

        # Set default max_new_tokens (HuggingFace defaults to only 20 tokens)
        kwargs.setdefault("max_new_tokens", 2048)

        # generate response
        output_ids = self.model.generate(
            **inputs,
            pad_token_id=self.tokenizer.eos_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
            **kwargs,
        )

        end_time = time.time()
        generation_time = end_time - start_time

        completion = self.tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1] :],  # only take the newly generated content
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        ).strip()

        # Calculate output tokens
        output_tokens = output_ids.shape[1] - input_tokens

        # Store minimal essential metrics
        self.last_generation_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_time_seconds": round(generation_time, 3),
            "model_memory_gb": model_memory_gb,
        }

        # If schema was provided, parse and validate the JSON response
        if schema:
            response_dict = json.loads(completion)
            validate_llm_response(response_dict, schema)
            return response_dict

        return completion
