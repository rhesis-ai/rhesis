import json
from typing import List, Optional, Type, Union

import litellm
from litellm import completion, image_generation
from pydantic import BaseModel

from rhesis.sdk.errors import NO_MODEL_NAME_PROVIDED
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.models.capabilities import CapabilityMixin
from rhesis.sdk.models.content import ContentPart, Message
from rhesis.sdk.models.utils import validate_llm_response

# Suppress debug info and prevent API key leaks in logs/exceptions
litellm.suppress_debug_info = True
litellm.redact_messages_in_exceptions = True
litellm.redact_user_api_key_info = True


class LiteLLM(BaseLLM, CapabilityMixin):
    PROVIDER: str

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        """
        LiteLLM: LiteLLM Provider for Model inference

        This class provides an interface for interacting with all models accessible through LiteLLM.

        Args:
            model_name (str): The name of the model to use including the provider.
            api_key (Optional[str]): The API key for authentication.
             If not provided, LiteLLM will handle it internally.

        Usage:
            >>> llm = LiteLLM(model_name="provider/model", api_key="your_api_key")
            >>> result = llm.generate(prompt="Tell me a joke.", system_prompt="You are funny")
            >>> print(result)

        If a Pydantic schema is provided to `generate`, the response will be validated and returned
        as a dict.
        """
        self.api_key = api_key  # LiteLLM will handle Environment Retrieval
        if not model_name or not isinstance(model_name, str) or model_name.strip() == "":
            raise ValueError(NO_MODEL_NAME_PROVIDED)
        super().__init__(model_name)

    def load_model(self):
        """
        LiteLLM handles model loading internally, so no loading is needed
        """
        pass

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        *args,
        **kwargs,
    ) -> Union[str, dict]:
        """
        Run a chat completion using LiteLLM, returning the response.
        The schema will be used to validate the response if provided.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Either a Pydantic model or OpenAI-wrapped JSON schema dict

        Returns:
            str or dict: Raw text if no schema, validated dict if schema provided
        """
        # handle system prompt
        messages = (
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
            if system_prompt
            else [{"role": "user", "content": prompt}]
        )

        # Handle schema format for LiteLLM
        # Dict schemas must already be in OpenAI-wrapped format
        # LiteLLM can handle both Pydantic models and OpenAI-wrapped dicts directly
        response_format = schema

        # Call the completion function passing given arguments
        response = completion(
            model=self.model_name,
            messages=messages,
            response_format=response_format,
            api_key=self.api_key,
            *args,
            **kwargs,
        )

        response_content = response.choices[0].message.content  # type: ignore
        if schema:
            response_content = json.loads(response_content)
            validate_llm_response(response_content, schema)
            return response_content
        else:
            return response_content

    @classmethod
    def get_available_models(cls) -> List[str]:
        models_list = litellm.get_valid_models(
            custom_llm_provider=cls.PROVIDER,
            check_provider_endpoint=False,
        )
        # Remove provider prefix from model names
        models_list = [model.replace(cls.PROVIDER + "/", "") for model in models_list]
        # Remove vision models from the list
        models_list = [model for model in models_list if "vision" not in model]
        # Remove embedding models from the list
        models_list = [model for model in models_list if "embedding" not in model]
        # Remove audio models from the list
        models_list = [model for model in models_list if "audio" not in model]
        # Remove image models from the list
        models_list = [model for model in models_list if "image" not in model]
        # Remove video models from the list
        models_list = [model for model in models_list if "video" not in model]

        return models_list

    def generate_multimodal(
        self,
        messages: List[Message],
        schema: Optional[Union[Type[BaseModel], dict]] = None,
        **kwargs,
    ) -> Union[str, dict]:
        """Generate a response from multimodal messages (text + images/audio/video/files).

        Args:
            messages: List of Message objects with mixed content
            schema: Optional schema for structured output
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            String response or dict if schema provided

        Raises:
            ValueError: If model doesn't support required modalities
        """
        # Check if any message contains non-text content
        has_images = False
        has_audio = False
        has_video = False

        for msg in messages:
            if isinstance(msg.content, list):
                for part in msg.content:
                    if isinstance(part, str):
                        continue
                    part_type = getattr(part, "type", None)
                    if part_type == "image":
                        has_images = True
                    elif part_type == "audio":
                        has_audio = True
                    elif part_type == "video":
                        has_video = True

        # Check capabilities
        if has_images and not self.supports_vision:
            raise ValueError(
                f"Model {self.model_name} does not support vision/image inputs. "
                f"Use a vision-capable model like gemini-2.0-flash or gpt-4o."
            )

        if has_audio and not self.supports_audio:
            raise ValueError(
                f"Model {self.model_name} does not support audio inputs. "
                f"Use an audio-capable model like gemini-1.5-pro."
            )

        if has_video and not self.supports_video:
            raise ValueError(
                f"Model {self.model_name} does not support video inputs. "
                f"Use a video-capable model like gemini-1.5-pro."
            )

        # Convert messages to LiteLLM format
        litellm_messages = [msg.to_litellm_format() for msg in messages]

        # Call completion
        response = completion(
            model=self.model_name,
            messages=litellm_messages,
            response_format=schema,
            api_key=self.api_key,
            **kwargs,
        )

        response_content = response.choices[0].message.content
        if schema:
            response_content = json.loads(response_content)
            validate_llm_response(response_content, schema)
            return response_content
        return response_content

    def analyze_content(
        self,
        content: Union[ContentPart, List[ContentPart]],
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Convenience method to analyze content with a text prompt.

        Args:
            content: Single ContentPart or list of ContentPart objects
            prompt: Question about the content
            system_prompt: Optional system instruction
            **kwargs: Additional parameters

        Returns:
            Text analysis/description

        Raises:
            ValueError: If model doesn't support the content type
        """
        # Normalize content to list
        if not isinstance(content, list):
            content = [content]

        # Check capabilities based on content types
        for part in content:
            part_type = getattr(part, "type", None)
            if part_type == "image" and not self.supports_vision:
                raise ValueError(
                    f"Model {self.model_name} does not support vision. Use a vision-capable model."
                )
            elif part_type == "audio" and not self.supports_audio:
                raise ValueError(
                    f"Model {self.model_name} does not support audio. Use an audio-capable model."
                )
            elif part_type == "video" and not self.supports_video:
                raise ValueError(
                    f"Model {self.model_name} does not support video. Use a video-capable model."
                )

        # Build messages
        messages = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))

        # Create user message with content + prompt
        user_content = list(content) + [prompt]
        messages.append(Message(role="user", content=user_content))

        return self.generate_multimodal(messages, **kwargs)

    def generate_image(
        self, prompt: str, n: int = 1, size: str = "1024x1024", **kwargs
    ) -> Union[str, list[str]]:
        """Generate images from a text prompt using LiteLLM's image generation.

        Args:
            prompt: Text description of the image to generate
            n: Number of images to generate (default: 1)
            size: Image size (e.g., "1024x1024", "512x512")
            **kwargs: Additional provider-specific parameters

        Returns:
            URL(s) of generated image(s). Single URL if n=1, list if n>1

        Example:
            >>> model = get_model("vertex_ai", "imagegeneration@006")
            >>> url = model.generate_image("A serene mountain landscape at sunset")
            >>> # Or for multiple images
            >>> urls = model.generate_image("A cute cat", n=3)
        """
        try:
            response = image_generation(
                model=self.model_name, prompt=prompt, n=n, size=size, api_key=self.api_key, **kwargs
            )

            # Extract URLs/data from response
            # Different providers return different response structures
            urls = []
            for img in response.data:
                # Try to get URL first (OpenAI, DALL-E)
                if hasattr(img, "url") and img.url:
                    urls.append(img.url)
                # Try to get base64 data (Vertex AI, some others)
                elif hasattr(img, "b64_json") and img.b64_json:
                    urls.append(f"data:image/png;base64,{img.b64_json}")
                # Try direct data attribute
                elif hasattr(img, "data"):
                    urls.append(img.data)
                else:
                    # Fallback: convert object to dict and look for common fields
                    img_dict = (
                        img
                        if isinstance(img, dict)
                        else (img.__dict__ if hasattr(img, "__dict__") else {})
                    )
                    url = img_dict.get("url") or img_dict.get("b64_json") or img_dict.get("data")
                    if url:
                        if "b64_json" in img_dict:
                            urls.append(f"data:image/png;base64,{url}")
                        else:
                            urls.append(url)

            if not urls:
                raise ValueError(f"No image data returned from {self.model_name}")

            # Return single URL if n=1, list otherwise
            return urls[0] if n == 1 else urls

        except Exception as e:
            raise ValueError(
                f"Image generation failed with {self.model_name}: {str(e)}. "
                f"Make sure the model supports image generation."
            ) from e
