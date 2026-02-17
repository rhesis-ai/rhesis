import gc
import json
import time
from typing import Any, List, Optional, Type

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

try:
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.integrations.transformers import (
        build_transformers_prefix_allowed_tokens_fn,
    )
except ImportError:
    raise ImportError(
        "LM Format Enforcer is not installed.\n"
        "Please install it with:\n"
        "  pip install rhesis-sdk[huggingface]\n"
        "or:\n"
        "  uv sync --extra huggingface\n"
        "Note: lmformatenforcer is included in the huggingface extras."
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


class LMFormatEnforcerLLM(BaseLLM):
    """
    LM Format Enforcer provider for guaranteed schema-compliant generation.

    This provider uses the lmformatenforcer library to enforce JSON schema constraints
    during generation, ensuring 100% schema compliance without relying on prompt engineering.

    When a schema is provided, constrained decoding is used to guarantee valid JSON output.
    When no schema is provided, behaves identically to HuggingFaceLLM.

    Example usage:
        >>> from rhesis.sdk.models.factory import get_model
        >>> from pydantic import BaseModel
        >>>
        >>> class OutputSchema(BaseModel):
        ...     answer: str
        ...     confidence: float
        >>>
        >>> llm = get_model("lmformatenforcer", "meta-llama/Llama-2-7b-chat-hf")
        >>> result = llm.generate(
        ...     "What is 2+2?",
        ...     schema=OutputSchema
        ... )
        >>> print(result)  # Guaranteed to match OutputSchema

        >>> # Can also be used in synthesizers
        >>> from rhesis.sdk.synthesizers import PromptSynthesizer
        >>> synthesizer = PromptSynthesizer(
        ...     prompt="Generate tests for a chatbot",
        ...     model="lmformatenforcer/meta-llama/Llama-2-7b-chat-hf"
        ... )
    """

    PROVIDER = "lmformatenforcer"

    def __init__(
        self,
        model_name: str,
        auto_loading: bool = True,
        generate_kwargs: Optional[dict] = None,
        gpu_only: bool = False,
        load_kwargs: Optional[dict] = None,
        custom_results_dir: Optional[str] = None,
        model_path: Optional[str] = None,
    ):
        """
        Initialize the LM Format Enforcer model.

        Args:
            model_name: The HuggingFace model ID or local path
            auto_loading: Whether to automatically load the model on initialization.
                If False, manual loading is needed via load_model().
            generate_kwargs: Default kwargs to pass to generate()
            gpu_only: If True, restrict model to GPU only (no CPU/disk offloading).
                Will raise an error if model doesn't fit in available GPU memory.
            load_kwargs: Additional kwargs to pass to AutoModelForCausalLM.from_pretrained()
            custom_results_dir: Optional custom directory for results
                (unused, kept for compatibility)
            model_path: Optional local path to pre-downloaded model. If provided, loads from
                this path instead of downloading from HuggingFace Hub.
        """
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)

        self.model_name = model_name
        self.model_path = model_path
        self.generate_kwargs = generate_kwargs
        self.gpu_only = gpu_only
        self.load_kwargs = load_kwargs or {}
        self.custom_results_dir = custom_results_dir

        self.model = None
        self.tokenizer = None
        self.device = None
        self.last_generation_metadata = None

        if auto_loading:
            self.load_model()

    def __del__(self):
        """
        Unload model and tokenizer to free up resources.
        """
        if self.model is not None or self.tokenizer is not None:
            self.unload_model()

    def load_model(self):
        """
        Load the model and tokenizer from the specified location.

        If model_path is provided, loads from that local path.
        Otherwise, downloads from HuggingFace Hub.

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
                    "gpu_only=True but CUDA is not available. Cannot load model without GPU."
                )
            device_map = "auto"
            print("Loading model with gpu_only=True (device_map='auto', multi-GPU enabled)")
        else:
            device_map = "auto"

        # Determine the source (local path or HuggingFace model ID)
        model_source = self.model_path if self.model_path else self.model_name

        if self.model_path:
            print(f"Loading model from local path: {self.model_path}")
        else:
            print(f"Loading model from HuggingFace Hub: {self.model_name}")

        # Configure kwargs based on whether we have a local path
        load_kwargs = {**self.load_kwargs}

        if self.model_path:
            # Local path - need trust_remote_code for custom model architectures
            load_kwargs["trust_remote_code"] = True

        # Load model and tokenizer
        self.model = AutoModelForCausalLM.from_pretrained(
            model_source,
            device_map=device_map,
            **load_kwargs,
        )

        # Tokenizer loaded WITHOUT trust_remote_code to avoid config dict/object issues
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_source,
        )

        # Get the device for input tensors
        if hasattr(self.model, "hf_device_map"):
            # Model is split across devices - get the device of the first module
            first_device = next(iter(self.model.hf_device_map.values()))
            self.device = torch.device(first_device)

            # If gpu_only, verify no layers were offloaded to CPU/disk
            if self.gpu_only:
                offloaded_devices = set(self.model.hf_device_map.values())
                non_gpu_devices = [d for d in offloaded_devices if str(d) == "cpu"]
                if non_gpu_devices:
                    raise RuntimeError(
                        f"gpu_only=True but model has layers offloaded to: {non_gpu_devices}. "
                        f"The model is too large for available GPU memory."
                    )
        else:
            # Model is on a single device
            self.device = self.model.device

        print(f"Model loaded successfully on device: {self.device}")
        return self

    def unload_model(self):
        """
        Aggressively unload the model and tokenizer to free up GPU/CPU memory.
        """
        try:
            if self.model is not None:
                try:
                    self.model.cpu()
                except Exception:
                    pass
                try:
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
        """
        if self.model is None:
            return 0.0

        try:
            param_size = sum(p.numel() * p.element_size() for p in self.model.parameters())
            buffer_size = sum(b.numel() * b.element_size() for b in self.model.buffers())
            total_bytes = param_size + buffer_size
            return round(total_bytes / (1024**3), 3)
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

        When a schema is provided, uses LM Format Enforcer to guarantee schema compliance
        through constrained decoding. When no schema is provided, behaves like standard
        HuggingFace generation.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional Pydantic BaseModel for structured output with guaranteed compliance
            **kwargs: Additional generation parameters (e.g., max_new_tokens, temperature)

        Returns:
            str if no schema provided, dict if schema provided (guaranteed to match schema)

        Raises:
            RuntimeError: If model or tokenizer is not loaded
            json.JSONDecodeError: If schema is provided but output is not valid JSON
        """
        # Check model and tokenizer
        if self.model is None or self.tokenizer is None:
            raise RuntimeError(HUGGINGFACE_MODEL_NOT_LOADED)

        # Merge generate_kwargs
        if self.generate_kwargs:
            kwargs = {**self.generate_kwargs, **kwargs}

        # Build prefix function for constrained decoding if schema is provided
        prefix_function = None
        if schema:
            json_schema = schema.model_json_schema()

            # Create parser and build prefix function for constrained decoding
            parser = JsonSchemaParser(json_schema)
            prefix_function = build_transformers_prefix_allowed_tokens_fn(self.tokenizer, parser)

            # Add schema instruction to prompt to help the model understand the task
            schema_instruction = (
                f"\n\nYou must respond with valid JSON matching this schema:\n"
                f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
                f"Only return the JSON object, nothing else."
            )
            prompt = prompt + schema_instruction

        # Format input with chat template if available
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
            # Fallback to simple concatenation
            messages = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            inputs = self.tokenizer(messages, return_tensors="pt")

        # Move inputs to the model's device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Capture metrics
        input_tokens = inputs["input_ids"].shape[1]
        model_memory_gb = self._get_model_memory_gb()
        start_time = time.time()

        # Set default max_new_tokens
        kwargs.setdefault("max_new_tokens", 2048)

        # Generate response with optional constrained decoding
        generation_kwargs = {
            **inputs,
            "pad_token_id": self.tokenizer.eos_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
            **kwargs,
        }

        if prefix_function is not None:
            generation_kwargs["prefix_allowed_tokens_fn"] = prefix_function

        output_ids = self.model.generate(**generation_kwargs)

        end_time = time.time()
        generation_time = end_time - start_time

        # Decode only the newly generated content
        completion = self.tokenizer.decode(
            output_ids[0][inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        ).strip()

        # Calculate output tokens
        output_tokens = output_ids.shape[1] - input_tokens

        # Store metrics
        self.last_generation_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_time_seconds": round(generation_time, 3),
            "model_memory_gb": model_memory_gb,
            "constrained_decoding": schema is not None,
        }

        # If schema was provided, parse and validate the JSON response
        if schema:
            response_dict = json.loads(completion)
            validate_llm_response(response_dict, schema)
            return response_dict

        return completion

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
        **kwargs: Any,
    ) -> List[Any]:
        """
        Batch processing is not implemented for LMFormatEnforcerLLM.

        Constrained decoding with LM Format Enforcer is currently designed for
        single-sequence generation. Use generate() in a loop for multiple prompts.
        """
        raise NotImplementedError(
            "generate_batch is not implemented for LMFormatEnforcerLLM. "
            "Please use generate() in a loop for multiple prompts."
        )
