import json
import logging
import os
import re
from typing import Generator, List

from dotenv import load_dotenv

from rhesis.sdk import RhesisClient, collaborate
from rhesis.sdk.models.factory import get_model

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Rhesis Client for collaborative testing
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
                return file.read().strip()
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

    def stream_assistant_response(
        self, prompt: str, conversation_history: List[dict] = None
    ) -> Generator[str, None, None]:
        """Stream the assistant's response using SDK model with conversation history.

        Args:
            prompt: The current user message
            conversation_history: List of previous messages in format [{"role": "user/assistant", "content": "..."}]
        """
        try:
            # Build the full prompt with conversation history
            full_prompt = self.use_case_system_prompt + "\n\n"

            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history:
                    role = "User" if msg["role"] == "user" else "Assistant"
                    full_prompt += f"{role}: {msg['content']}\n\n"

            # Add current prompt
            full_prompt += f"User: {prompt}\n\nAssistant:"

            # Vertex AI via LiteLLM has issues with streaming (CustomStreamWrapper)
            # Use non-streaming response which works reliably
            response = self.model.generate(full_prompt, stream=False)

            # Yield the complete response
            if isinstance(response, str):
                yield response
            else:
                # Try to extract content from response object
                try:
                    if hasattr(response, "choices") and len(response.choices) > 0:
                        content = response.choices[0].message.content
                        yield content if content else ""
                    else:
                        yield str(response) if response else ""
                except Exception:
                    yield str(response) if response else ""

        except Exception as e:
            logger.error(f"Error in stream_assistant_response: {str(e)}")
            yield (
                "I apologize, but I couldn't process your request at this time "
                "due to an unexpected error."
            )

    def generate_context(self, prompt: str) -> List[str]:
        """Generate context fragments for a prompt."""
        try:
            # Create system prompt for context generation with explicit JSON format instructions
            context_system_prompt = """
                You are a helpful assistant that provides relevant context fragments for user questions.
                For the given user query, generate 3-5 short, relevant context fragments that would be helpful for answering the question.
                
                IMPORTANT: You MUST respond with ONLY a valid JSON object that has a "fragments" key containing an array of strings.
                Example format:
                {
                    "fragments": [
                        "Context fragment 1",
                        "Context fragment 2",
                        "Context fragment 3"
                    ]
                }
                
                Do not include any explanations, markdown formatting, or additional text outside of the JSON object.
                """

            # Combine system prompt with user question
            full_prompt = (
                f"{context_system_prompt}\n\n"
                f"Generate context fragments for this insurance question: {prompt}"
            )

            # Get response from SDK model
            response = self.model.generate(full_prompt)

            # Parse the response
            response_text = response if isinstance(response, str) else str(response)
            return self._parse_context_response(response_text, prompt)

        except Exception as e:
            logger.error(f"Error in generate_context: {str(e)}")
            return self._get_default_fragments(prompt)

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

        # If we still have no fragments, create default ones based on the prompt
        if not fragments:
            return self._get_default_fragments(prompt)

        return fragments[:5]  # Return up to 5 fragments

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


def get_response_generator(use_case: str = "insurance") -> ResponseGenerator:
    """Get a ResponseGenerator instance for the specified use case."""
    return ResponseGenerator(use_case)


# Public API functions that maintain backward compatibility
def get_assistant_response(
    prompt: str, use_case: str = "insurance", conversation_history: List[dict] = None
) -> str:
    """Get a complete response from the assistant with optional conversation history."""
    response_generator = get_response_generator(use_case)
    return "".join(response_generator.stream_assistant_response(prompt, conversation_history))


@collaborate(name="echo", description="Echo the input")
def echo(input: str) -> str:
    return input


@collaborate(name="multiply_numbers", description="Multiply two numbers")
def multiply_numbers(a: int, b: int) -> dict:
    return {
        "result": a * b,
        "error": None,
        "success": True,
        "message": f"The result of {a} * {b} is {a * b}",
    }


@collaborate(
    name="stream_assistant_response", description="Stream assistant responses for insurance queries"
)
def stream_assistant_response(
    prompt: str, use_case: str = "insurance", conversation_history: List[dict] = None
) -> Generator[str, None, None]:
    """Stream the assistant's response with optional conversation history.

    This function is decorated with @collaborate to enable remote testing
    from the Rhesis platform.

    Args:
        prompt: The current user message
        use_case: The use case to use for the system prompt
        conversation_history: List of previous messages in format [{"role": "user/assistant", "content": "..."}]
    """
    logger.info("=" * 80)
    logger.info("🔵 COLLABORATIVE TEST EXECUTION STARTED")
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
        logger.error(f"❌ Error during collaborative test execution: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.info("=" * 80)
        raise


def generate_context(prompt: str, use_case: str = "insurance") -> List[str]:
    """Generate context fragments for a prompt."""
    response_generator = get_response_generator(use_case)
    return response_generator.generate_context(prompt)
