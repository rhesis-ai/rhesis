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

# Multimodal Content Errors
IMAGE_CONTENT_MISSING_DATA = (
    "ImageContent must have either 'url' or 'data'. "
    "Use ImageContent.from_url(), from_file(), from_bytes(), or from_base64()."
)
AUDIO_CONTENT_MISSING_DATA = (
    "AudioContent must have either 'url' or 'data'. "
    "Use AudioContent.from_url(), from_file(), from_bytes(), or from_base64()."
)
FILE_CONTENT_MISSING_DATA = (
    "FileContent must have either 'url' or 'data'. "
    "Use FileContent.from_url(), from_file(), from_bytes(), or from_base64()."
)
VIDEO_FILE_TOO_LARGE = (
    "Video file too large: {size_mb:.1f}MB exceeds {max_size_mb}MB limit. "
    "Consider uploading to cloud storage and using VideoContent.from_url() instead."
)
VIDEO_FILE_NOT_FOUND = "Video file not found: {path}"

# Multimodal Capability Errors
MODEL_NO_VISION_SUPPORT = (
    "Model {model_name} does not support vision/image inputs. "
    "Use a vision-capable model like gemini-2.0-flash or gpt-4o."
)
MODEL_NO_AUDIO_SUPPORT = (
    "Model {model_name} does not support audio inputs. "
    "Use an audio-capable model like gemini-1.5-pro."
)
MODEL_NO_VIDEO_SUPPORT = (
    "Model {model_name} does not support video inputs. "
    "Use a video-capable model like gemini-1.5-pro."
)
MODEL_NO_PDF_SUPPORT = (
    "Model {model_name} does not support PDF/document inputs. "
    "Use a vision-capable model like gemini-2.0-flash or gpt-4o."
)
