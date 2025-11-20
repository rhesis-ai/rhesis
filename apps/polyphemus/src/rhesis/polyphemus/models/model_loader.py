import logging
import os
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

logger = logging.getLogger("rhesis-polyphemus")


class ModelLoader:
    def __init__(self):
        self.model = None
        self.tokenizer = None

    async def load_model(self):
        """Initialize model and tokenizer"""
        # Get model name from environment variable
        model_name = os.environ.get("HF_MODEL", "cognitivecomputations/Dolphin3.0-Llama3.1-8B")
        hf_token = os.environ.get("HF_TOKEN", None)

        logger.info(f"Loading model: {model_name}")
        start_time = time.time()

        try:
            # Check if GPU is available
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device}")

            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=hf_token)

            # Quantization config for better memory efficiency
            quantization_config = None
            if device == "cuda":
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )

            # Load model with optimizations
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=quantization_config,
                device_map="auto",
                use_auth_token=hf_token,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                attn_implementation="flash_attention_2" if device == "cuda" else None,
            )

            # Compile model for speedup if using PyTorch 2.0+
            if hasattr(torch, "compile") and device == "cuda":
                try:
                    logger.info("Compiling model with torch.compile()...")
                    self.model = torch.compile(self.model)
                    logger.info("Model compilation successful")
                except Exception as e:
                    logger.warning(f"Model compilation failed, continuing without compilation: {e}")

            logger.info(f"Model loaded successfully in {time.time() - start_time:.2f} seconds")
            return True
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False

    def get_gpu_info(self):
        """Get GPU information"""
        gpu_info = {}
        if torch.cuda.is_available():
            try:
                gpu_info = {
                    "device_name": torch.cuda.get_device_name(0),
                    "device_count": torch.cuda.device_count(),
                    "memory_allocated_MB": round(torch.cuda.memory_allocated(0) / 1024**2, 2),
                    "memory_reserved_MB": round(torch.cuda.memory_reserved(0) / 1024**2, 2),
                    "max_memory_MB": round(
                        torch.cuda.get_device_properties(0).total_memory / 1024**2, 2
                    ),
                }
            except Exception as e:
                gpu_info = {"error": str(e)}
        return gpu_info
