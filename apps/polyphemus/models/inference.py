import torch
import logging
from transformers import TextIteratorStreamer
from typing import Dict, Optional, AsyncGenerator

logger = logging.getLogger("rhesis-polyphemus")

def format_prompt(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Format the prompt for Dolphin/Llama models"""
    # Dolphin 3.0 expects a specific prompt format for best results
    if system_prompt:
        formatted_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    else:
        formatted_prompt = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    
    return formatted_prompt

class InferenceEngine:
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
    
    async def generate_text(self, 
                          prompt: str, 
                          max_tokens: int = 512,
                          temperature: float = 0.7,
                          top_p: float = 0.9,
                          top_k: int = 50,
                          repetition_penalty: float = 1.1,
                          system_prompt: Optional[str] = None) -> Dict:
        """Generate text (non-streaming)"""
        start_time = torch.cuda.Event(enable_timing=True) if torch.cuda.is_available() else None
        end_time = torch.cuda.Event(enable_timing=True) if torch.cuda.is_available() else None
        
        if start_time:
            start_time.record()
        else:
            start_time_cpu = torch.tensor(0.).cpu()
            
        # Format prompt
        formatted_prompt = format_prompt(prompt, system_prompt)
        logger.info(f"Generating with formatted prompt: {formatted_prompt[:100]}...")
        
        # Prepare inputs
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
        
        # Generate
        generation_config = {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id
        }
        
        with torch.no_grad():
            output = self.model.generate(**inputs, **generation_config)
        
        # Decode output
        full_output = self.tokenizer.decode(output[0], skip_special_tokens=True)
        
        # Extract just the assistant's response
        assistant_output = full_output[len(self.tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)):]
        
        # Clean up any memory not needed
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            end_time.record()
            torch.cuda.synchronize()
            generation_time = start_time.elapsed_time(end_time) / 1000.0  # Convert from ms to seconds
        else:
            end_time_cpu = torch.tensor(0.).cpu()
            generation_time = end_time_cpu - start_time_cpu
            
        logger.info(f"Generation completed in {generation_time:.2f} seconds")
        
        return {
            "generated_text": assistant_output.strip(),
            "tokens_generated": len(output[0]) - len(inputs["input_ids"][0]),
            "generation_time_seconds": generation_time
        }
    
    async def generate_stream(self, 
                            prompt: str,
                            max_tokens: int = 512,
                            temperature: float = 0.7,
                            top_p: float = 0.9,
                            top_k: int = 50,
                            repetition_penalty: float = 1.1,
                            system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        formatted_prompt = format_prompt(prompt, system_prompt)
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(self.model.device)
        
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        generation_config = {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
            "do_sample": temperature > 0,
            "streamer": streamer,
        }
        
        # Start generation in a separate thread
        from threading import Thread
        thread = Thread(target=self.model.generate, kwargs={**inputs, **generation_config})
        thread.start()
        
        # Stream the output
        for text in streamer:
            yield f"data: {text}\n\n"
        
        yield "data: [DONE]\n\n" 