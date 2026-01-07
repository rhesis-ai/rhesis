import json
import logging
import os
import re
from typing import Generator, List, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from rhesis.sdk import RhesisClient, endpoint, observe
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
                role = "User" if msg["role"] == "user" else "Assistant"
                full_prompt += f"{role}: {msg['content']}\n\n"

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
            logger.error(f"Error in stream_assistant_response: {str(e)}")
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
            else:
                # Fallback parsing if structured output not supported
                return self._parse_intent_fallback(str(intent_result))

        except Exception as e:
            logger.error(f"Error in recognize_intent: {str(e)}")
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
        "output": "{{ result.intent }}",
        "metadata": {
            "confidence": "{{ result.confidence }}",
            "intent": "{{ result.intent }}",
        },
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
