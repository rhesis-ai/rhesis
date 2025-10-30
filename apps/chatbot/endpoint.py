import json
import logging
import os
import re
from typing import Generator, List

from dotenv import load_dotenv

from rhesis.sdk.models.factory import get_model

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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

    def get_assistant_response(self, prompt: str) -> str:
        """Get a complete response from the assistant."""
        return "".join(self.stream_assistant_response(prompt))

    def stream_assistant_response(self, prompt: str) -> Generator[str, None, None]:
        """Stream the assistant's response using SDK model."""
        try:
            # Combine system prompt with user prompt
            full_prompt = f"{self.use_case_system_prompt}\n\nUser: {prompt}\n\nAssistant:"

            # Use SDK model's generate method with streaming
            # Note: SDK models handle streaming internally
            response = self.model.generate(full_prompt, stream=True)

            # Stream the response
            if hasattr(response, "__iter__"):
                for chunk in response:
                    if chunk:
                        # Handle different streaming response structures
                        try:
                            # Standard LiteLLM structure: chunk.choices[0].delta.content
                            if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                                delta = chunk.choices[0].delta
                                if hasattr(delta, "content") and delta.content:
                                    yield delta.content
                            # Handle plain string chunks
                            elif isinstance(chunk, str):
                                yield chunk
                            # Handle CustomStreamWrapper or other wrapper objects
                            # Try to extract text content directly
                            elif hasattr(chunk, "text"):
                                if chunk.text:
                                    yield chunk.text
                            elif hasattr(chunk, "content"):
                                if chunk.content:
                                    yield chunk.content
                            else:
                                # Last resort: try to convert to string
                                chunk_str = str(chunk) if chunk else ""
                                if chunk_str and not chunk_str.startswith(
                                    "<"
                                ):  # Avoid object repr strings
                                    yield chunk_str
                        except (AttributeError, IndexError):
                            # If the structure is different, try to convert to string
                            chunk_str = str(chunk) if chunk else ""
                            if chunk_str and not chunk_str.startswith(
                                "<"
                            ):  # Avoid object repr strings
                                yield chunk_str
            else:
                # If streaming is not supported, yield the entire response
                yield response

        except Exception as e:
            logger.error(f"Error in stream_assistant_response: {str(e)}")
            yield "I apologize, but I couldn't process your request at this time due to an unexpected error."

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
            full_prompt = f"{context_system_prompt}\n\nGenerate context fragments for this insurance question: {prompt}"

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
        except:
            pass

        # If JSON extraction fails, try to extract just the array
        try:
            array_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', text)
            if array_match:
                array_str = array_match.group(0)
                fragments = json.loads(array_str)
                if isinstance(fragments, list):
                    return fragments[:5]
        except:
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
def get_assistant_response(prompt: str, use_case: str = "insurance") -> str:
    """Get a complete response from the assistant."""
    response_generator = get_response_generator(use_case)
    return response_generator.get_assistant_response(prompt)


def stream_assistant_response(
    prompt: str, use_case: str = "insurance"
) -> Generator[str, None, None]:
    """Stream the assistant's response."""
    response_generator = get_response_generator(use_case)
    return response_generator.stream_assistant_response(prompt)


def generate_context(prompt: str, use_case: str = "insurance") -> List[str]:
    """Generate context fragments for a prompt."""
    response_generator = get_response_generator(use_case)
    return response_generator.generate_context(prompt)
