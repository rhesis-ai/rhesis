import json
import logging
import os
import re
from typing import Generator, List

from dotenv import load_dotenv
from opentelemetry import trace

from rhesis.sdk import RhesisClient
from rhesis.sdk.models.factory import get_model

# Get tracer for explicit span creation
tracer = trace.get_tracer(__name__)

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
        with tracer.start_as_current_span(
            "function.load_system_prompt",
            attributes={
                "use_case": self.use_case,
            },
        ) as span:
            try:
                # Get the directory of the current script
                current_dir = os.path.dirname(os.path.abspath(__file__))
                prompt_file = os.path.join(current_dir, "use_cases", f"{self.use_case}.md")

                with open(prompt_file, "r", encoding="utf-8") as file:
                    content = file.read().strip()
                    span.set_attribute("prompt_length", len(content))
                    span.set_attribute("prompt_file", prompt_file)
                    return content
            except FileNotFoundError:
                logger.error(f"System prompt file not found: use_cases/{self.use_case}.md")
                span.set_attribute("error", "file_not_found")
                # Fallback to a basic prompt
                return "You are a helpful assistant. Please provide clear and helpful responses."
            except Exception as e:
                logger.error(f"Error loading system prompt: {str(e)}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
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
            conversation_history: List of previous messages in format
                [{"role": "user/assistant", "content": "..."}]
        """
        with tracer.start_as_current_span(
            "function.stream_response",
            attributes={
                "use_case": self.use_case,
                "prompt_length": len(prompt),
                "has_history": conversation_history is not None,
                "history_length": len(conversation_history) if conversation_history else 0,
            },
        ) as parent_span:
            try:
                # Build the full prompt with conversation history
                with tracer.start_as_current_span(
                    "function.build_conversation_context",
                    attributes={
                        "history_messages": len(conversation_history) if conversation_history else 0
                    },
                ) as context_span:
                    full_prompt = self.use_case_system_prompt + "\n\n"

                    # Add conversation history if provided
                    if conversation_history:
                        for msg in conversation_history:
                            role = "User" if msg["role"] == "user" else "Assistant"
                            full_prompt += f"{role}: {msg['content']}\n\n"

                    # Add current prompt
                    full_prompt += f"User: {prompt}\n\nAssistant:"
                    context_span.set_attribute("total_prompt_length", len(full_prompt))

                # Invoke LLM with explicit span
                with tracer.start_as_current_span(
                    "ai.llm.invoke",
                    attributes={
                        "ai.operation.type": "llm.invoke",
                        "ai.model.provider": DEFAULT_GENERATION_MODEL,
                        "ai.model.name": DEFAULT_MODEL_NAME,
                        "ai.prompt.tokens": len(full_prompt.split()),  # Rough token estimate
                        "ai.streaming": False,
                    },
                ) as llm_span:
                    # Vertex AI via LiteLLM has issues with streaming (CustomStreamWrapper)
                    # Use non-streaming response which works reliably
                    response = self.model.generate(full_prompt, stream=False)

                    llm_span.set_attribute("ai.response.received", True)

                # Process response with explicit span
                with tracer.start_as_current_span("function.process_response") as process_span:
                    # Yield the complete response
                    if isinstance(response, str):
                        process_span.set_attribute("response_type", "string")
                        process_span.set_attribute("response_length", len(response))
                        parent_span.set_attribute("completion_tokens", len(response.split()))
                        yield response
                    else:
                        # Try to extract content from response object
                        try:
                            if hasattr(response, "choices") and len(response.choices) > 0:
                                content = response.choices[0].message.content
                                process_span.set_attribute("response_type", "choices_object")
                                process_span.set_attribute(
                                    "response_length", len(content) if content else 0
                                )
                                parent_span.set_attribute(
                                    "completion_tokens", len(content.split()) if content else 0
                                )
                                yield content if content else ""
                            else:
                                content = str(response) if response else ""
                                process_span.set_attribute("response_type", "fallback_string")
                                process_span.set_attribute("response_length", len(content))
                                yield content
                        except Exception as extract_error:
                            process_span.record_exception(extract_error)
                            content = str(response) if response else ""
                            yield content

            except Exception as e:
                logger.error(f"Error in stream_assistant_response: {str(e)}")
                parent_span.record_exception(e)
                parent_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                yield (
                    "I apologize, but I couldn't process your request at this time "
                    "due to an unexpected error."
                )

    def generate_context(self, prompt: str) -> List[str]:
        """Generate context fragments for a prompt."""
        with tracer.start_as_current_span(
            "function.generate_context",
            attributes={
                "use_case": self.use_case,
                "prompt": prompt[:100],  # First 100 chars
            },
        ) as parent_span:
            try:
                # Create system prompt for context generation with JSON format
                with tracer.start_as_current_span("function.build_context_prompt") as prompt_span:
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

                    # Combine system prompt with user question
                    full_prompt = (
                        f"{context_system_prompt}\n\n"
                        f"Generate context fragments for this insurance question: {prompt}"
                    )
                    prompt_span.set_attribute("prompt_length", len(full_prompt))

                # Invoke LLM for context generation
                with tracer.start_as_current_span(
                    "ai.llm.invoke",
                    attributes={
                        "ai.operation.type": "llm.invoke",
                        "ai.model.provider": DEFAULT_GENERATION_MODEL,
                        "ai.model.name": DEFAULT_MODEL_NAME,
                        "ai.purpose": "context_generation",
                    },
                ) as llm_span:
                    # Get response from SDK model
                    response = self.model.generate(full_prompt)
                    llm_span.set_attribute("ai.response.received", True)

                # Parse the response
                with tracer.start_as_current_span("function.parse_context") as parse_span:
                    response_text = response if isinstance(response, str) else str(response)
                    parse_span.set_attribute("response_length", len(response_text))

                    fragments = self._parse_context_response(response_text, prompt)
                    parse_span.set_attribute("fragments_count", len(fragments))
                    parent_span.set_attribute("context_fragments", len(fragments))

                    return fragments

            except Exception as e:
                logger.error(f"Error in generate_context: {str(e)}")
                parent_span.record_exception(e)
                parent_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                default_fragments = self._get_default_fragments(prompt)
                parent_span.set_attribute("used_default_fragments", True)
                return default_fragments

    def _parse_context_response(self, text: str, prompt: str) -> List[str]:
        """Parse the response text to extract context fragments."""
        with tracer.start_as_current_span(
            "function.parse_context_strategies",
            attributes={"text_length": len(text)},
        ) as span:
            # Try to parse the entire response as JSON
            with tracer.start_as_current_span("function.parse_direct_json") as json_span:
                try:
                    context_data = json.loads(text)
                    fragments = context_data.get("fragments", [])
                    if fragments and isinstance(fragments, list):
                        json_span.set_attribute("success", True)
                        span.set_attribute("parsing_strategy", "direct_json")
                        return fragments[:5]
                    json_span.set_attribute("success", False)
                except json.JSONDecodeError:
                    json_span.set_attribute("success", False)

            # If direct JSON parsing fails, try to extract JSON using regex
            with tracer.start_as_current_span("function.parse_regex_json") as regex_span:
                try:
                    json_match = re.search(r'(\{.*"fragments"\s*:\s*\[.*\].*\})', text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        context_data = json.loads(json_str)
                        fragments = context_data.get("fragments", [])
                        if fragments and isinstance(fragments, list):
                            regex_span.set_attribute("success", True)
                            span.set_attribute("parsing_strategy", "regex_json")
                            return fragments[:5]
                    regex_span.set_attribute("success", False)
                except Exception:
                    regex_span.set_attribute("success", False)

            # If JSON extraction fails, try to extract just the array
            with tracer.start_as_current_span("function.parse_array") as array_span:
                try:
                    array_match = re.search(r'\[\s*"[^"]*"(?:\s*,\s*"[^"]*")*\s*\]', text)
                    if array_match:
                        array_str = array_match.group(0)
                        fragments = json.loads(array_str)
                        if isinstance(fragments, list):
                            array_span.set_attribute("success", True)
                            span.set_attribute("parsing_strategy", "array_extraction")
                            return fragments[:5]
                    array_span.set_attribute("success", False)
                except Exception:
                    array_span.set_attribute("success", False)

            # If all structured parsing fails, extract text fragments
            with tracer.start_as_current_span("function.extract_text_fragments") as text_span:
                fragments = self._extract_text_fragments(text)
                text_span.set_attribute("fragments_found", len(fragments))

                if fragments:
                    span.set_attribute("parsing_strategy", "text_extraction")
                    return fragments[:5]

            # If we still have no fragments, create default ones based on the prompt
            span.set_attribute("parsing_strategy", "default_fallback")
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

    This function is decorated with @collaborate to enable remote testing
    from the Rhesis platform.

    Args:
        prompt: The current user message
        use_case: The use case to use for the system prompt
        conversation_history: List of previous messages in format
            [{"role": "user/assistant", "content": "..."}]
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
