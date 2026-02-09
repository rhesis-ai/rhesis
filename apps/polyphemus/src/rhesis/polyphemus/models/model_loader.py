"""
Model implementations for Polyphemus service.
Contains different model classes that can be used based on configuration.

Supports two inference engines:
- vLLM (default): High-performance inference with PagedAttention, continuous
  batching, and optimized CUDA kernels. 10-20x faster than HuggingFace.
- Transformers (fallback): Standard HuggingFace transformers via SDK.

Set INFERENCE_ENGINE=vllm (default) or INFERENCE_ENGINE=transformers.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("rhesis-polyphemus")

# Default model - can be overridden via environment variable
# For vLLM: use HuggingFace model name (e.g., "Qwen/Qwen2.5-8B-Instruct")
# For transformers: use provider/model format (e.g., "huggingface/distilgpt2")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "huggingface/distilgpt2")

# Inference engine: "vllm" (default, high-performance) or "transformers" (fallback)
INFERENCE_ENGINE = os.environ.get("INFERENCE_ENGINE", "vllm")

# Model path configuration - supports local path or GCS bucket location
# For GCS paths, the bucket should be mounted at /gcs-models via Cloud Run volume mount
MODEL_PATH = os.environ.get("MODEL_PATH", "")

# GCS volume mount path (Cloud Run mounts GCS bucket here)
GCS_MOUNT_PATH = "/gcs-models"


def _strip_provider_prefix(model_name: str) -> str:
    """
    Strip provider prefix from model name for vLLM compatibility.

    Converts:
    - "huggingface/Qwen/Qwen2.5-8B-Instruct" -> "Qwen/Qwen2.5-8B-Instruct"
    - "huggingface/distilgpt2" -> "distilgpt2"
    - "Qwen/Qwen2.5-8B-Instruct" -> "Qwen/Qwen2.5-8B-Instruct" (no change)
    """
    if model_name.startswith("huggingface/"):
        return model_name[len("huggingface/") :]
    return model_name


def _map_gcs_to_mounted_path(model_name: str, gcs_path: str) -> str:
    """
    Map GCS path to mounted volume path for Cloud Run.

    Cloud Run mounts GCS buckets at /gcs-models, so we convert:
    gs://bucket/path/to/model -> /gcs-models/path/to/model

    Args:
        model_name: Model identifier (e.g., "organization/model-name")
        gcs_path: GCS path (e.g., "gs://bucket-name/models")

    Returns:
        str: Local mounted path (e.g., "/gcs-models/models/model-name")
    """
    if not gcs_path.startswith("gs://"):
        return gcs_path

    # Parse GCS path: gs://bucket/path -> bucket, path
    bucket_and_path = gcs_path[5:]  # Remove "gs://"
    parts = bucket_and_path.split("/", 1)
    bucket_path = parts[1] if len(parts) > 1 else ""

    # Get model directory name from model_name
    model_dir_name = model_name.split("/")[-1]

    # Construct mounted path
    if bucket_path:
        mounted_path = f"{GCS_MOUNT_PATH}/{bucket_path}/{model_dir_name}"
    else:
        mounted_path = f"{GCS_MOUNT_PATH}/{model_dir_name}"

    logger.info(f"Mapped GCS path: {gcs_path}/{model_dir_name}")
    logger.info(f"To mounted path: {mounted_path}")

    return mounted_path


def _resolve_model_source(model_name: str) -> str:
    """
    Resolve model source from model name and MODEL_PATH configuration.

    Returns either a local path (from GCS mount or local disk) or
    a HuggingFace Hub model identifier.

    Args:
        model_name: Model identifier (already stripped of provider prefix)

    Returns:
        str: Resolved model path or HuggingFace identifier
    """
    if MODEL_PATH:
        if MODEL_PATH.startswith("gs://"):
            source = _map_gcs_to_mounted_path(model_name, MODEL_PATH)
            logger.info(f"Using Cloud Storage mounted volume: {source}")
            return source
        else:
            logger.info(f"Using local path: {MODEL_PATH}")
            return MODEL_PATH
    else:
        logger.info("No MODEL_PATH set, will use HuggingFace Hub")
        return model_name


class VLLMModelLoader:
    """
    vLLM-based model loader for high-performance GPU inference.

    Uses vLLM's optimized engine with PagedAttention, continuous batching,
    and optimized CUDA kernels for 10-20x speedup over HuggingFace transformers.

    Expected performance on NVIDIA L4 GPU:
    - 2k tokens in 5-15 seconds
    - Throughput: 100-200 tokens/second

    Configuration via environment variables:
    - GPU_MEMORY_UTILIZATION: Fraction of GPU memory to use (default: 0.9)
    - MAX_MODEL_LEN: Maximum sequence length (default: 8192)
    - VLLM_DTYPE: Data type for model weights (default: "half" for float16)
    - VLLM_ENFORCE_EAGER: Set to "1" to disable CUDA graphs (default: "0")
    - VLLM_TENSOR_PARALLEL_SIZE: Number of GPUs for tensor parallelism (default: 1)
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        auto_loading: bool = True,
    ):
        """
        Initialize vLLM model loader.

        Args:
            model_name: Model identifier. Supports formats:
                - "huggingface/org/model" (prefix stripped automatically)
                - "org/model" (used directly)
                - "model" (used directly)
            auto_loading: Whether to load the model immediately.
        """
        self._model_name = model_name or DEFAULT_MODEL
        self._auto_loading = auto_loading
        self._llm = None  # vLLM LLM instance
        self.model_name = self._model_name
        # Compatibility attributes (not used by vLLM but checked by services)
        self.model = None
        self.tokenizer = None

        if auto_loading:
            self.load_model()

    def load_model(self) -> "VLLMModelLoader":
        """
        Load the model using vLLM's optimized engine.

        Handles:
        - GCS paths (gs://...): maps to mounted volume at /gcs-models
        - Local paths: loads from local disk
        - HuggingFace Hub: downloads and caches automatically

        Returns:
            self: Returns self for method chaining
        """
        if self._llm is not None:
            logger.info("vLLM model already loaded, reusing")
            return self

        from vllm import LLM

        # Resolve model name (strip huggingface/ prefix for vLLM)
        hf_model_name = _strip_provider_prefix(self._model_name)
        model_source = _resolve_model_source(hf_model_name)

        # vLLM configuration from environment variables
        gpu_memory_utilization = float(os.environ.get("GPU_MEMORY_UTILIZATION", "0.9"))
        max_model_len = int(os.environ.get("MAX_MODEL_LEN", "8192"))
        dtype = os.environ.get("VLLM_DTYPE", "half")
        enforce_eager = os.environ.get("VLLM_ENFORCE_EAGER", "0") == "1"
        tensor_parallel_size = int(os.environ.get("VLLM_TENSOR_PARALLEL_SIZE", "1"))

        logger.info(f"Loading vLLM model: {model_source}")
        logger.info(
            f"vLLM config: gpu_mem={gpu_memory_utilization}, "
            f"max_model_len={max_model_len}, dtype={dtype}, "
            f"enforce_eager={enforce_eager}, "
            f"tensor_parallel_size={tensor_parallel_size}"
        )

        self._llm = LLM(
            model=model_source,
            gpu_memory_utilization=gpu_memory_utilization,
            dtype=dtype,
            max_model_len=max_model_len,
            trust_remote_code=True,
            enforce_eager=enforce_eager,
            tensor_parallel_size=tensor_parallel_size,
        )

        # Set sentinel values for compatibility checks in services.py
        self.model = "vllm-loaded"
        self.tokenizer = "vllm-loaded"

        # Log GPU information
        try:
            import torch

            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                allocated_gb = torch.cuda.memory_allocated() / 1e9
                reserved_gb = torch.cuda.memory_reserved() / 1e9
                logger.info(f"GPU: {gpu_name}")
                logger.info(
                    f"GPU Memory - Allocated: {allocated_gb:.2f}GB, Reserved: {reserved_gb:.2f}GB"
                )
        except Exception as gpu_error:
            logger.warning(f"Could not check GPU status: {gpu_error}")

        logger.info(f"vLLM model loaded successfully: {model_source}")
        return self

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Any] = None,
        **kwargs,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate a response using vLLM's optimized inference.

        Uses vLLM's chat() method for proper chat template handling
        with instruction-tuned models.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional schema (not yet supported with vLLM)
            **kwargs: Generation parameters:
                - temperature (float): Sampling temperature (default: 0.7)
                - max_tokens / max_new_tokens (int): Max output tokens
                - top_p (float): Nucleus sampling (default: 0.9)
                - top_k (int): Top-k sampling (-1 to disable)
                - repetition_penalty (float): Repetition penalty

        Returns:
            str: Generated text response
        """
        if self._llm is None:
            raise RuntimeError("vLLM model not loaded. Call load_model() first.")

        # Build chat messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Map kwargs to vLLM SamplingParams
        sampling_params = self._build_sampling_params(**kwargs)

        try:
            # Use chat() for proper chat template handling
            outputs = self._llm.chat(
                messages=[messages],
                sampling_params=sampling_params,
            )
        except Exception as chat_err:
            # Fallback to plain generate if chat template unavailable
            logger.warning(f"Chat template failed ({chat_err}), falling back to plain generate")
            # Build a simple prompt string
            full_prompt = ""
            if system_prompt:
                full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
            else:
                full_prompt = prompt
            outputs = self._llm.generate([full_prompt], sampling_params)

        if outputs and outputs[0].outputs:
            return outputs[0].outputs[0].text.strip()
        return ""

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Any] = None,
        **kwargs,
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Generate responses for multiple prompts using vLLM batch inference.

        vLLM excels at batch processing through its continuous batching
        scheduler, providing near-linear throughput scaling.

        Args:
            prompts: List of user prompts
            system_prompt: Optional system prompt (applied to all)
            schema: Optional schema (not yet supported with vLLM)
            **kwargs: Generation parameters (same as generate())

        Returns:
            List of generated text responses
        """
        if self._llm is None:
            raise RuntimeError("vLLM model not loaded. Call load_model() first.")

        # Build messages for each prompt
        all_messages = []
        for prompt in prompts:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            all_messages.append(messages)

        sampling_params = self._build_sampling_params(**kwargs)

        try:
            outputs = self._llm.chat(
                messages=all_messages,
                sampling_params=sampling_params,
            )
        except Exception as chat_err:
            logger.warning(f"Batch chat failed ({chat_err}), falling back to plain generate")
            plain_prompts = []
            for prompt in prompts:
                if system_prompt:
                    plain_prompts.append(f"System: {system_prompt}\n\nUser: {prompt}")
                else:
                    plain_prompts.append(prompt)
            outputs = self._llm.generate(plain_prompts, sampling_params)

        results = []
        for output in outputs:
            if output.outputs:
                results.append(output.outputs[0].text.strip())
            else:
                results.append("")
        return results

    def _build_sampling_params(self, **kwargs):
        """Build vLLM SamplingParams from generation kwargs."""
        from vllm import SamplingParams

        temperature = kwargs.get("temperature", 0.7)
        # Support both max_tokens and max_new_tokens (HuggingFace compat)
        max_tokens = kwargs.get("max_tokens", kwargs.get("max_new_tokens", 2048))
        top_p = kwargs.get("top_p", 0.9)
        top_k = kwargs.get("top_k", -1)
        # vLLM uses -1 to disable top_k (HuggingFace uses 0 or None)
        if top_k is None or top_k == 0:
            top_k = -1
        repetition_penalty = kwargs.get("repetition_penalty", 1.0)

        # vLLM requires temperature > 0 when sampling
        if temperature <= 0:
            temperature = 0.01

        return SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
        )

    @property
    def vllm_engine(self):
        """Access the underlying vLLM LLM engine."""
        return self._llm


class LazyModelLoader:
    """
    HuggingFace transformers-based model loader (fallback engine).

    Uses the SDK's get_model factory to load any supported model type
    (HuggingFace, OpenAI, Anthropic, etc.) based on the model name/type.

    This is the fallback inference engine. For production GPU deployments,
    use VLLMModelLoader instead (set INFERENCE_ENGINE=vllm).

    The model name can be specified in the format:
    - "provider/model-name" (e.g., "huggingface/distilgpt2", "openai/gpt-4o")
    - "model-name" (defaults to huggingface provider)
    """

    def __init__(self, model_name: Optional[str] = None, auto_loading: bool = True):
        """
        Initialize LazyModelLoader model.

        Args:
            model_name: Model identifier in format "provider/model" or just model name.
                If None, uses default model (huggingface/distilgpt2).
            auto_loading: Whether to automatically load the model on initialization.
                If False, model loading is deferred until load_model() is called.
        """
        # Use default model if not provided
        self._model_name = model_name or DEFAULT_MODEL
        self._auto_loading = auto_loading
        self._internal_model = None

        # Set model_name for BaseLLM compatibility (don't call super().__init__
        # as it would trigger load_model immediately)
        self.model_name = self._model_name
        self.model = None
        self.tokenizer = None

        if auto_loading:
            self.load_model()

    def load_model(self):
        """
        Load the model using the SDK's get_model factory.

        If MODEL_PATH is configured:
        - For GCS paths (gs://...): maps to mounted volume at /gcs-models
        - For local paths: loads from local disk
        - If not set: uses HuggingFace Hub to download

        The model can be any supported type (HuggingFace, OpenAI, etc.)
        based on the model_name format.

        Returns:
            self: Returns self for method chaining
        """
        if self._internal_model is None:
            from rhesis.sdk.models.factory import get_model

            logger.info(f"Loading model: {self._model_name}")

            # Determine the model source to use (local path or Hub identifier)
            model_source = None
            if MODEL_PATH:
                # Check if it's a GCS path and map to mounted volume
                if MODEL_PATH.startswith("gs://"):
                    model_source = _map_gcs_to_mounted_path(self._model_name, MODEL_PATH)
                    logger.info(f"Using Cloud Storage mounted volume at: {model_source}")
                else:
                    # Use local path directly
                    model_source = MODEL_PATH
                    logger.info(f"Using local path: {model_source}")
            else:
                # No MODEL_PATH set - will download from HuggingFace Hub
                logger.info("No MODEL_PATH set, will use HuggingFace Hub")

            # Configure load_kwargs for optimal GPU performance
            # Use FP16 for best performance on L4 GPU
            # Enable caching and optimizations
            # Note: device_map is handled automatically by HuggingFace SDK, don't set it here
            import torch

            default_load_kwargs = {
                "torch_dtype": torch.float16,  # FP16 for faster inference on GPU
                "use_cache": True,  # Enable KV-cache for faster generation
                "low_cpu_mem_usage": True,  # Optimize CPU memory during loading
            }

            # Allow override via environment variable for advanced configurations
            # Support both base64-encoded (LOAD_KWARGS_B64) and plain JSON (LOAD_KWARGS)
            # Examples:
            # - 8-bit: LOAD_KWARGS='{"load_in_8bit": true}'
            # - 4-bit: LOAD_KWARGS='{"load_in_4bit": true}'
            # - FP16: LOAD_KWARGS='{"torch_dtype":"float16","use_cache":true}'
            load_kwargs_env = os.environ.get("LOAD_KWARGS_B64") or os.environ.get("LOAD_KWARGS")
            if load_kwargs_env:
                import base64
                import json

                try:
                    # If it's base64-encoded, decode it first
                    if os.environ.get("LOAD_KWARGS_B64"):
                        load_kwargs_json = base64.b64decode(load_kwargs_env).decode("utf-8")
                        logger.info("Decoding LOAD_KWARGS from base64")
                    else:
                        load_kwargs_json = load_kwargs_env

                    parsed_kwargs = json.loads(load_kwargs_json)

                    # Handle torch_dtype string conversion
                    if "torch_dtype" in parsed_kwargs:
                        dtype_str = parsed_kwargs["torch_dtype"]
                        if isinstance(dtype_str, str):
                            if dtype_str == "float16" or dtype_str == "fp16":
                                parsed_kwargs["torch_dtype"] = torch.float16
                            elif dtype_str == "float32" or dtype_str == "fp32":
                                parsed_kwargs["torch_dtype"] = torch.float32
                            elif dtype_str == "bfloat16" or dtype_str == "bf16":
                                parsed_kwargs["torch_dtype"] = torch.bfloat16

                    # Merge with defaults, allowing override
                    default_load_kwargs.update(parsed_kwargs)
                    logger.info(f"Using custom load_kwargs from env: {default_load_kwargs}")
                except (json.JSONDecodeError, base64.binascii.Error) as e:
                    logger.warning(
                        f"Invalid LOAD_KWARGS (error: {e}), using default: {default_load_kwargs}"
                    )

            logger.info(f"Loading with configuration: {default_load_kwargs}")

            try:
                self._internal_model = get_model(
                    self._model_name,
                    auto_loading=False,
                    model_path=model_source,
                    load_kwargs=default_load_kwargs,
                )
            except TypeError:
                # If model_path is not supported by this model type, try without it
                logger.info("model_path not supported for this model type, creating without it")
                self._internal_model = get_model(self._model_name, auto_loading=False)

            # Load the model (for HuggingFace models, this loads model and tokenizer)
            if hasattr(self._internal_model, "load_model"):
                self._internal_model.load_model()

            # Set model attribute for compatibility
            if hasattr(self._internal_model, "model"):
                self.model = self._internal_model.model
            if hasattr(self._internal_model, "tokenizer"):
                self.tokenizer = self._internal_model.tokenizer

            # Try to optimize with BetterTransformer (PyTorch 2.0+ optimization)
            # This can provide 1.5-2x speedup for inference
            # Requires: pip install optimum
            if hasattr(self._internal_model, "model"):
                try:
                    from optimum.bettertransformer import BetterTransformer

                    logger.info("Applying BetterTransformer optimization...")
                    self._internal_model.model = BetterTransformer.transform(
                        self._internal_model.model, keep_original_model=False
                    )
                    self.model = self._internal_model.model
                    logger.info("✅ BetterTransformer applied successfully (1.5-2x speedup)")
                except ImportError:
                    logger.info(
                        "⚠️ BetterTransformer not available (optional). "
                        "Install 'optimum' package for 1.5-2x inference speedup."
                    )
                except Exception as bt_error:
                    logger.warning(
                        f"BetterTransformer optimization failed: {bt_error}. "
                        f"Continuing without optimization."
                    )

            # GPU monitoring: Verify model is on GPU and log memory usage
            if hasattr(self._internal_model, "model"):
                try:
                    import torch

                    if torch.cuda.is_available():
                        # Check device of model parameters
                        first_param = next(self._internal_model.model.parameters(), None)
                        if first_param is not None:
                            device = first_param.device
                            logger.info(f"✅ Model on device: {device}")

                            # Log GPU memory usage
                            allocated_gb = torch.cuda.memory_allocated() / 1e9
                            reserved_gb = torch.cuda.memory_reserved() / 1e9
                            logger.info(
                                f"✅ GPU Memory - Allocated: {allocated_gb:.2f}GB, "
                                f"Reserved: {reserved_gb:.2f}GB"
                            )

                            # Log GPU name
                            gpu_name = torch.cuda.get_device_name(0)
                            logger.info(f"✅ GPU: {gpu_name}")

                            # VERIFY: Test GPU computation
                            try:
                                test_tensor = torch.randn(1000, 1000, device=device)
                                result = torch.matmul(test_tensor, test_tensor)
                                logger.info(
                                    f"✅ GPU Computation Test: PASSED "
                                    f"(result device: {result.device})"
                                )
                                del test_tensor, result
                                torch.cuda.empty_cache()
                            except Exception as compute_error:
                                logger.error(f"❌ GPU Computation Test: FAILED - {compute_error}")
                        else:
                            logger.warning("⚠️ Model has no parameters to check device")
                    else:
                        logger.warning("⚠️ CUDA not available - model may be on CPU!")
                except Exception as gpu_error:
                    logger.warning(f"Could not check GPU status: {gpu_error}")

            logger.info(f"Model loaded successfully: {self._model_name}")

        return self

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Any] = None,
        **kwargs,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate a response using the loaded model.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional schema for structured output
            **kwargs: Additional generation parameters

        Returns:
            str or dict: Generated response
        """
        if self._internal_model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Delegate to the internal model
        return self._internal_model.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            schema=schema,
            **kwargs,
        )

    def generate_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        schema: Optional[Any] = None,
        **kwargs,
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Generate responses for multiple prompts using the loaded model.

        Falls back to sequential generation if batch processing is not supported
        by the underlying provider (e.g., lmformatenforcer, huggingface).

        Args:
            prompts: List of user prompts
            system_prompt: Optional system prompt (applied to all prompts)
            schema: Optional schema for structured output
            **kwargs: Additional generation parameters

        Returns:
            List of str or dict: Generated responses
        """
        if self._internal_model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        try:
            # Try batch processing first (works for API-based providers)
            return self._internal_model.generate_batch(
                prompts=prompts,
                system_prompt=system_prompt,
                schema=schema,
                **kwargs,
            )
        except (NotImplementedError, AttributeError):
            # Fallback to sequential generation for providers that don't support batch.
            # Catches NotImplementedError (method exists but raises) and AttributeError
            # (method doesn't exist, e.g., if provider doesn't inherit from BaseLLM properly).
            logger.info(
                f"Batch processing not supported by {self._model_name}, "
                f"falling back to sequential generation"
            )
            results = []
            for prompt in prompts:
                result = self._internal_model.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    schema=schema,
                    **kwargs,
                )
                results.append(result)
            return results
