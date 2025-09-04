# Error messages used in the SDK. This file makes it easier to find and edit the used Error messages

# For this file too long lines are fine for better readability
# flake8: noqa: E501


# LLM Errors
NO_MODEL_NAME_PROVIDED = "The model name is not valid. Please provide a non-empty string."
HUGGINGFACE_MODEL_NOT_LOADED = "Hugging Face model is not loaded. Set auto_loading=True to load it manually using `load_model()`."
MODEL_RELOAD_WARNING = "WARNING: The model {} is already loaded. It will be reloaded."
WARNING_TOKENIZER_ALREADY_LOADED_RELOAD = (
    "WARNING: The tokenizer for model {} is already loaded. It will be reloaded."
)
