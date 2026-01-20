import json
import logging
import os
import re
from typing import Generator, List, Literal, Optional, Union

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from rhesis.sdk import RhesisClient, endpoint, observe
from rhesis.sdk.models import ImageContent, Message
from rhesis.sdk.models.factory import get_model

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Rhesis Client for remote endpoint testing
rhesis_client = RhesisClient(
    api_key=os.getenv("RHESIS_API_KEY"),
    project_id=os.getenv("RHESIS_PROJECT_ID"),
    environment=os.getenv("RHESIS_ENVIRONMENT", "development"),
)

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 10  # seconds

# Model configuration - uses SDK providers approach
DEFAULT_GENERATION_MODEL = os.getenv("DEFAULT_GENERATION_MODEL", "vertex_ai")
DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "gemini-2.5-flash")

# Image generation model configuration
IMAGE_GENERATION_MODEL = os.getenv("IMAGE_GENERATION_MODEL", "gemini")
IMAGE_GENERATION_MODEL_NAME = os.getenv("IMAGE_GENERATION_MODEL_NAME", "imagen-4.0-generate-001")


class IntentClassification(BaseModel):
    """Schema for intent classification result."""

    intent: Literal["informational", "transactional", "support", "complaint"] = Field(
        description="The classified intent category"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level of the classification"
    )


def get_llm_model():
    """Get the configured LLM model using SDK factory."""
    try:
        return get_model(provider=DEFAULT_GENERATION_MODEL, model_name=DEFAULT_MODEL_NAME)
    except Exception as e:
        logger.error(f"Failed to initialize LLM model: {str(e)}")
        raise ValueError(f"Could not initialize LLM model: {str(e)}")


class ResponseGenerator:
    """Class to generate responses using SDK model providers."""

    def __init__(self, use_case: str = "insurance"):
        """Initialize with SDK model and use case."""
        self.model = get_llm_model()
        self.use_case = use_case
        self.use_case_system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt from the corresponding .md file in use_cases folder."""
        try:
            # Get the directory of the current script
            current_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_file = os.path.join(current_dir, "use_cases", f"{self.use_case}.md")

            with open(prompt_file, "r", encoding="utf-8") as file:
                content = file.read().strip()
                return content
        except FileNotFoundError:
            logger.error(f"System prompt file not found: use_cases/{self.use_case}.md")
            # Fallback to a basic prompt
            return "You are a helpful assistant. Please provide clear and helpful responses."
        except Exception as e:
            logger.error(f"Error loading system prompt: {str(e)}")
            return "You are a helpful assistant. Please provide clear and helpful responses."

    def get_assistant_response(self, prompt: str, conversation_history: List[dict] = None) -> str:
        """Get a complete response from the assistant with optional conversation history."""
        return "".join(self.stream_assistant_response(prompt, conversation_history))

    @observe()
    def _build_conversation_prompt(
        self, prompt: str, conversation_history: List[dict] = None
    ) -> str:
        """Build the full prompt with conversation history."""
        full_prompt = self.use_case_system_prompt + "\n\n"

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                if isinstance(msg, dict):
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    content = msg.get("content", "")
                    full_prompt += f"{role}: {content}\n\n"
                elif isinstance(msg, str):
                    # If it's a string, treat it as user message
                    full_prompt += f"User: {msg}\n\n"

        # Add current prompt
        full_prompt += f"User: {prompt}\n\nAssistant:"
        return full_prompt

    @observe.llm(
        provider=DEFAULT_GENERATION_MODEL,
        model=DEFAULT_MODEL_NAME,
    )
    def _invoke_llm(self, full_prompt: str) -> str:
        """Invoke the LLM model to generate a response."""
        # Vertex AI via LiteLLM has issues with streaming (CustomStreamWrapper)
        # Use non-streaming response which works reliably
        response = self.model.generate(full_prompt, stream=False)
        return response

    @observe()
    def _extract_response_content(self, response) -> str:
        """Extract text content from LLM response."""
        if isinstance(response, str):
            return response

        # Try to extract content from response object
        if hasattr(response, "choices") and len(response.choices) > 0:
            content = response.choices[0].message.content
            return content if content else ""

        # Fallback to string conversion
        return str(response) if response else ""

    @observe()
    def stream_assistant_response(
        self, prompt: str, conversation_history: List[dict] = None
    ) -> Generator[str, None, None]:
        """Stream the assistant's response using SDK model with conversation history.

        Args:
            prompt: The current user message
            conversation_history: List of previous messages in format
                [{"role": "user/assistant", "content": "..."}]
        """
        try:
            # Build the full prompt with conversation history
            full_prompt = self._build_conversation_prompt(prompt, conversation_history)

            # Invoke LLM
            response = self._invoke_llm(full_prompt)

            # Extract and yield content
            content = self._extract_response_content(response)
            yield content

        except Exception as e:
            logger.error(f"Error in stream_assistant_response: {str(e)}", exc_info=True)
            yield (
                "I apologize, but I couldn't process your request at this time "
                "due to an unexpected error."
            )

    @observe()
    def _build_context_prompt(self, prompt: str) -> str:
        """Build the prompt for context generation."""
        context_system_prompt = """
            You are a helpful assistant that provides relevant context
            fragments for user questions.
            For the given user query, generate 3-5 short, relevant context
            fragments that would be helpful for answering the question.
            
            IMPORTANT: You MUST respond with ONLY a valid JSON object that
            has a "fragments" key containing an array of strings.
            Example format:
            {
                "fragments": [
                    "Context fragment 1",
                    "Context fragment 2",
                    "Context fragment 3"
                ]
            }
            
            Do not include any explanations, markdown formatting, or
            additional text outside of the JSON object.
            """

        full_prompt = (
            f"{context_system_prompt}\n\n"
            f"Generate context fragments for this insurance question: {prompt}"
        )
        return full_prompt

    @observe.llm(
        provider=DEFAULT_GENERATION_MODEL,
        model=DEFAULT_MODEL_NAME,
        purpose="context_generation",
    )
    def _generate_context_fragments_llm(self, full_prompt: str) -> str:
        """Invoke LLM to generate context fragments."""
        response = self.model.generate(full_prompt)
        return response

    @observe()
    def generate_context(self, prompt: str) -> List[str]:
        """Generate context fragments for a prompt."""
        try:
            # Build prompt
            full_prompt = self._build_context_prompt(prompt)

            # Invoke LLM for context generation
            response = self._generate_context_fragments_llm(full_prompt)

            # Parse the response
            response_text = response if isinstance(response, str) else str(response)
            fragments = self._parse_context_response(response_text, prompt)

            return fragments

        except Exception as e:
            logger.error(f"Error in generate_context: {str(e)}")
            default_fragments = self._get_default_fragments(prompt)
            return default_fragments

    @observe()
    def _parse_context_response(self, text: str, prompt: str) -> List[str]:
        """Parse the response text to extract context fragments."""
        # Try to parse the entire response as JSON
        try:
            context_data = json.loads(text)
            fragments = context_data.get("fragments", [])
            if fragments and isinstance(fragments, list):
                return fragments[:5]
        except json.JSONDecodeError:
            pass

        # If direct JSON parsing fails, try to extract JSON using regex
        try:
            json_match = re.search(r'(\{.*"fragments"\s*:\s*\[.*\].*\})', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                context_data = json.loads(json_str)
                fragments = context_data.get("fragments", [])
                if fragments and isinstance(fragments, list):
                    return fragments[:5]
        except Exception:
            pass

        # If JSON extraction fails, try to extract just the array
        try:
            array_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', text)
            if array_match:
                array_str = array_match.group(0)
                fragments = json.loads(array_str)
                if isinstance(fragments, list):
                    return fragments[:5]
        except Exception:
            pass

        # If all structured parsing fails, extract text fragments
        fragments = self._extract_text_fragments(text)
        if fragments:
            return fragments[:5]

        # If we still have no fragments, create default ones based on the prompt
        return self._get_default_fragments(prompt)

    def _extract_text_fragments(self, text: str) -> List[str]:
        """Extract text fragments from unstructured text."""
        fragments = []

        # Extract bullet points or numbered items
        bullet_items = re.findall(r"(?:^|\n)[•\-*]\s*(.*?)(?=(?:\n[•\-*])|$)", text, re.MULTILINE)
        if bullet_items:
            fragments.extend(bullet_items)

        # Extract numbered items if no bullet points found
        if not fragments:
            numbered_items = re.findall(
                r"(?:^|\n)\d+\.\s*(.*?)(?=(?:\n\d+\.)|$)", text, re.MULTILINE
            )
            if numbered_items:
                fragments.extend(numbered_items)

        # If still no fragments, split by newlines and take non-empty lines
        if not fragments:
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            fragments.extend(lines)

        return fragments

    def _get_default_fragments(self, prompt: str) -> List[str]:
        """Get default context fragments based on the prompt."""
        return [
            f"Information about {prompt}",
            f"Key concepts related to {prompt}",
            f"Common questions about {prompt}",
        ]

    @observe()
    def _build_intent_classification_prompt(self, prompt: str) -> str:
        """Build the prompt for intent classification."""
        classification_system_prompt = """
You are an intent classification system. Your task is to classify user prompts
into one of four categories.

**Intent Categories:**

1. **informational** - User is seeking information or knowledge
   Examples:
   - "How does homeowner's insurance work?"
   - "What is comprehensive coverage?"
   - "Can you explain deductibles?"

2. **transactional** - User wants to perform an action or complete a transaction
   Examples:
   - "I want to file a claim"
   - "Please update my policy"
   - "Can you help me purchase additional coverage?"

3. **support** - User needs help with a problem or technical issue
   Examples:
   - "I'm having trouble logging into my account"
   - "I need help understanding my bill"
   - "My claim status isn't showing correctly"

4. **complaint** - User is expressing dissatisfaction or frustration
   Examples:
   - "My claim has been pending for too long"
   - "I'm not satisfied with the service"
   - "This process is too complicated"

**Instructions:**
- Analyze the user's prompt carefully
- Choose the most appropriate category: informational, transactional, support, or complaint
- Assess confidence: high (clear intent), medium (somewhat ambiguous), low (very ambiguous)
"""

        full_prompt = f"{classification_system_prompt}\n\nClassify this user prompt: {prompt}"
        return full_prompt

    @observe.llm(
        provider=DEFAULT_GENERATION_MODEL,
        model=DEFAULT_MODEL_NAME,
        purpose="intent_classification",
    )
    def _classify_intent_llm(self, full_prompt: str) -> IntentClassification:
        """Invoke LLM to classify intent with structured output."""
        response = self.model.generate(full_prompt, schema=IntentClassification)
        return response

    @observe()
    def recognize_intent(self, prompt: str) -> dict:
        """Recognize intent from a user prompt.

        Args:
            prompt: User's message/prompt to classify

        Returns:
            Dict with intent and confidence
        """
        try:
            # Build classification prompt
            full_prompt = self._build_intent_classification_prompt(prompt)

            # Invoke LLM for intent classification with Pydantic schema
            intent_result = self._classify_intent_llm(full_prompt)

            # Convert Pydantic model to dict
            if isinstance(intent_result, IntentClassification):
                return intent_result.model_dump()
            elif isinstance(intent_result, dict):
                return intent_result
            elif isinstance(intent_result, str):
                # If it's a string, try to parse as JSON
                return self._parse_intent_fallback(intent_result)
            else:
                # Fallback parsing if structured output not supported
                return self._parse_intent_fallback(str(intent_result))

        except Exception as e:
            logger.error(f"Error in recognize_intent: {str(e)}", exc_info=True)
            # Return default intent on error
            return {"intent": "informational", "confidence": "low"}

    @observe()
    def _parse_intent_fallback(self, text: str) -> dict:
        """Fallback parser for intent classification response."""
        # Try to parse as JSON
        try:
            intent_data = json.loads(text)
            if "intent" in intent_data:
                return {
                    "intent": intent_data.get("intent", "informational"),
                    "confidence": intent_data.get("confidence", "low"),
                }
        except json.JSONDecodeError:
            pass

        # Try to extract JSON using regex
        try:
            json_match = re.search(r'(\{.*"intent"\s*:\s*"[^"]*".*\})', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                intent_data = json.loads(json_str)
                return {
                    "intent": intent_data.get("intent", "informational"),
                    "confidence": intent_data.get("confidence", "low"),
                }
        except Exception:
            pass

        # If all parsing fails, return default
        logger.warning(f"Failed to parse intent response: {text[:100]}")
        return {"intent": "informational", "confidence": "low"}

    @observe()
    def get_multimodal_response(
        self,
        message: str,
        conversation_history: Optional[List[dict]] = None,
        image_urls: Optional[List[str]] = None,
        image_data: Optional[List[str]] = None,
    ) -> str:
        """Generate response with image analysis support.

        Args:
            message: User's text message
            conversation_history: Previous conversation messages
            image_urls: List of image URLs to analyze
            image_data: List of base64-encoded images

        Returns:
            Assistant's response text
        """
        try:
            # Check if model supports vision
            if not self.model.supports_vision:
                return (
                    "I apologize, but the current model doesn't support image analysis. "
                    "Please contact support to enable vision-capable models."
                )

            # Use image_analysis use case for better prompts
            analysis_generator = ResponseGenerator("image_analysis")

            # Build messages with multimodal content
            messages = []

            # Add system prompt for image analysis
            messages.append(
                Message(role="system", content=analysis_generator.use_case_system_prompt)
            )

            # Add conversation history
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    messages.append(Message(role=role, content=content))

            # Build current user message with images and text
            user_content = []

            # Add images first
            if image_urls:
                for url in image_urls:
                    user_content.append(ImageContent.from_url(url))

            if image_data:
                import base64

                for img_data in image_data:
                    # Handle base64 data (with or without data URI prefix)
                    if img_data.startswith("data:"):
                        # Extract base64 part
                        img_data = img_data.split(",", 1)[1]
                    # Decode and create ImageContent
                    decoded = base64.b64decode(img_data)
                    user_content.append(ImageContent.from_bytes(decoded, "image/jpeg"))

            # Add text message
            user_content.append(message)

            messages.append(Message(role="user", content=user_content))

            # Generate response using multimodal capability with analysis specialist
            response = analysis_generator.model.generate_multimodal(messages)

            return response if isinstance(response, str) else str(response)

        except Exception as e:
            logger.error(f"Error in get_multimodal_response: {str(e)}", exc_info=True)
            return (
                "I apologize, but I encountered an error while analyzing the images. "
                "Please try again or contact support if the issue persists."
            )

    @observe()
    def generate_image(
        self, prompt: str, n: int = 1, size: str = "1024x1024", **kwargs
    ) -> Union[str, List[str]]:
        """Generate images from text prompt.

        Args:
            prompt: Text description of image to generate
            n: Number of images to generate
            size: Image size (e.g., "1024x1024")
            **kwargs: Additional provider-specific parameters

        Returns:
            Single image URL if n=1, list of URLs otherwise
        """
        try:
            # Use image_generation use case for better prompt enhancement
            generation_generator = ResponseGenerator("image_generation")

            # Enhance the prompt using the generation specialist
            enhanced_prompt_request = (
                f"Enhance this image generation prompt for professional quality: {prompt}"
            )
            enhanced_prompt = generation_generator.model.generate(enhanced_prompt_request)

            # Get a separate image generation model
            image_model = get_model(
                provider=IMAGE_GENERATION_MODEL, model_name=IMAGE_GENERATION_MODEL_NAME
            )

            # Check if model supports image generation
            if not hasattr(image_model, "generate_image"):
                raise ValueError(
                    f"Model {IMAGE_GENERATION_MODEL}/{IMAGE_GENERATION_MODEL_NAME} "
                    "doesn't support image generation. "
                    "Try setting IMAGE_GENERATION_MODEL=gemini and "
                    "IMAGE_GENERATION_MODEL_NAME=imagen-4.0-generate-001"
                )

            # Use enhanced prompt for generation
            final_prompt = enhanced_prompt if isinstance(enhanced_prompt, str) else prompt
            return image_model.generate_image(final_prompt, n=n, size=size, **kwargs)

        except Exception as e:
            logger.error(f"Error in generate_image: {str(e)}", exc_info=True)
            raise ValueError(f"Image generation failed: {str(e)}")

    @observe()
    def edit_image(self, image_data: str, edit_prompt: str) -> str:
        """Edit an image based on text instructions.

        Args:
            image_data: Base64-encoded image data
            edit_prompt: Instructions for how to edit the image

        Returns:
            URL or base64 data of the edited image
        """
        try:
            # Use image_editing use case for specialized editing guidance
            editing_generator = ResponseGenerator("image_editing")

            # First, analyze the original image
            import base64

            decoded = base64.b64decode(image_data)
            image_content = ImageContent.from_bytes(decoded, "image/jpeg")

            # Build analysis prompt using editing specialist
            analysis_messages = [
                Message(role="system", content=editing_generator.use_case_system_prompt),
                Message(
                    role="user",
                    content=[
                        image_content,
                        (
                            f"Analyze this image and create a detailed prompt for generating "
                            f"an edited version with these modifications: {edit_prompt}. "
                            f"Include all important visual elements that should be preserved "
                            f"and specify exactly what should be changed."
                        ),
                    ],
                ),
            ]

            # Get detailed description for editing using editing specialist
            if not editing_generator.model.supports_vision:
                raise ValueError("Current model doesn't support image editing (requires vision)")

            description = editing_generator.model.generate_multimodal(analysis_messages)

            # Now generate the edited image based on the description
            image_model = get_model(
                provider=IMAGE_GENERATION_MODEL, model_name=IMAGE_GENERATION_MODEL_NAME
            )

            if not hasattr(image_model, "generate_image"):
                raise ValueError("Image editing requires an image generation model")

            # Create edit prompt combining original description with edits
            generation_prompt = (
                f"Based on this image description, create the edited version: {description}"
            )

            edited_image = image_model.generate_image(generation_prompt, n=1, size="1024x1024")

            return edited_image if isinstance(edited_image, str) else edited_image[0]

        except Exception as e:
            logger.error(f"Error in edit_image: {str(e)}", exc_info=True)
            raise ValueError(f"Image editing failed: {str(e)}")


def get_response_generator(use_case: str = "insurance") -> ResponseGenerator:
    """Get a ResponseGenerator instance for the specified use case."""
    return ResponseGenerator(use_case)


def get_assistant_response(
    prompt: str, use_case: str = "insurance", conversation_history: List[dict] = None
) -> str:
    """Get a complete response from the assistant with optional conversation history."""
    response_generator = get_response_generator(use_case)
    return "".join(response_generator.stream_assistant_response(prompt, conversation_history))


def stream_assistant_response(
    prompt: str, use_case: str = "insurance", conversation_history: List[dict] = None
) -> Generator[str, None, None]:
    """Stream the assistant's response with optional conversation history.

    This function is decorated with @endpoint to enable remote testing
    from the Rhesis platform.

    Args:
        prompt: The current user message
        use_case: The use case to use for the system prompt
        conversation_history: List of previous messages in format
            [{"role": "user/assistant", "content": "..."}]
    """
    logger.info("=" * 80)
    logger.info("🔵 REMOTE TEST EXECUTION STARTED")
    logger.info(f"Prompt: {prompt}")
    logger.info(f"Use case: {use_case}")
    logger.info(f"Conversation history: {conversation_history}")
    logger.info("=" * 80)

    try:
        response_generator = get_response_generator(use_case)
        logger.info("Response generator created successfully")

        result_generator = response_generator.stream_assistant_response(
            prompt, conversation_history
        )
        logger.info("Starting to stream response...")

        # Stream and log chunks
        chunk_count = 0
        for chunk in result_generator:
            chunk_count += 1
            if chunk_count <= 3:  # Log first 3 chunks
                logger.info(
                    f"Chunk {chunk_count}: {chunk[:50]}..."
                    if len(chunk) > 50
                    else f"Chunk {chunk_count}: {chunk}"
                )
            yield chunk

        logger.info(f"✅ Streaming complete. Total chunks: {chunk_count}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error during remote test execution: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.info("=" * 80)
        raise


def generate_context(prompt: str, use_case: str = "insurance") -> List[str]:
    """Generate context fragments for a prompt."""
    response_generator = get_response_generator(use_case)
    return response_generator.generate_context(prompt)


@endpoint(
    name="recognize_intent",
    description="Classify user intent from a prompt",
    request_mapping={
        "prompt": "{{ input }}",
        "use_case": "{{ use_case | default('insurance') }}",
    },
    response_mapping={
        "output": "{{ intent }}",
        "metadata": "{{ {'intent': intent, 'confidence': confidence} | tojson }}",
    },
)
def recognize_intent_endpoint(prompt: str, use_case: str = "insurance") -> dict:
    """
    Standalone SDK endpoint for testing intent recognition.

    Args:
        prompt: User's message/prompt to classify
        use_case: Use case for context (default: "insurance")

    Returns:
        Intent classification result with intent and confidence
    """
    logger.info("=" * 80)
    logger.info("🔵 INTENT RECOGNITION ENDPOINT")
    logger.info(f"Prompt: {prompt}")
    logger.info(f"Use case: {use_case}")
    logger.info("=" * 80)

    try:
        response_generator = get_response_generator(use_case)
        logger.info("Response generator created successfully")

        result = response_generator.recognize_intent(prompt)

        logger.info(f"✅ Intent recognized: {result}")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ Error during intent recognition: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.info("=" * 80)
        raise
