import json
import logging
import os
import re
from typing import Generator, List

from dotenv import load_dotenv

from rhesis.sdk import RhesisClient, endpoint
from rhesis.sdk.models.factory import get_model

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Rhesis Client for collaborative testing
rhesis_client = RhesisClient.from_environment()

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
            conversation_history: List of previous messages in format
                [{"role": "user/assistant", "content": "..."}]
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
            # Create system prompt for context generation with JSON format
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


# =============================================================================
# AUTO-MAPPING TEST FUNCTIONS (HIGH CONFIDENCE)
# =============================================================================
# These functions use standard parameter names that should auto-map with high confidence


@endpoint(name="test_standard_naming", description="Test function with standard parameter names")
def test_standard_naming(
    input: str,
    session_id: str = None,
    context: List[str] = None,
    metadata: dict = None,
    tool_calls: List[dict] = None,
) -> dict:
    """Test auto-mapping with exact standard field names.

    Expected: High confidence auto-mapping (1.0)
    All parameters match standard patterns exactly.
    """
    return {
        "output": f"Processed: {input}",
        "session_id": session_id or "auto_generated_session",
        "context": context or [],
        "metadata": {"processed": True, "original_metadata": metadata},
        "tool_calls": tool_calls or [],
    }


@endpoint(name="test_partial_standard", description="Test with some standard naming")
def test_partial_standard(input: str, session_id: str = None) -> dict:
    """Test auto-mapping with partial standard naming.

    Expected: Medium-high confidence (0.6 - input + session_id matched)
    Missing: context, metadata, tool_calls
    """
    return {
        "output": f"Response to: {input}",
        "session_id": session_id,
    }


@endpoint(name="test_input_only", description="Test with only input parameter")
def test_input_only(input: str) -> dict:
    """Test auto-mapping with only input parameter.

    Expected: Low confidence (0.4 - only input matched)
    Should still auto-map but with lower confidence.
    """
    return {"output": f"Echo: {input}"}


# =============================================================================
# AUTO-MAPPING TEST FUNCTIONS (PATTERN VARIATIONS)
# =============================================================================
# These test variations of standard patterns


@endpoint(name="test_input_variations", description="Test input field variations")
def test_input_variations(message: str, conversation_id: str = None) -> dict:
    """Test auto-mapping with pattern variations.

    Expected: High confidence
    (message matches INPUT patterns, conversation_id matches SESSION patterns)
    message → maps to input
    conversation_id → maps to session_id
    """
    return {
        "result": f"Processed message: {message}",
        "conversation_id": conversation_id or "new_conv",
    }


@endpoint(name="test_compound_patterns", description="Test compound field names")
def test_compound_patterns(
    user_message: str, conv_id: str = None, context_docs: List[str] = None
) -> dict:
    """Test auto-mapping with compound naming patterns.

    Expected: High confidence
    user_message → maps to input
    conv_id → maps to session_id
    context_docs → maps to context
    """
    return {
        "response": f"Reply to: {user_message}",
        "conv_id": conv_id,
        "sources": context_docs,
    }


@endpoint(name="test_suffix_patterns", description="Test _id suffix patterns")
def test_suffix_patterns(query: str, session_id: str = None, thread_id: str = None) -> dict:
    """Test auto-mapping with _id suffixes.

    Expected: High confidence
    query → maps to input
    session_id → exact match
    thread_id → matches SESSION patterns
    """
    return {"answer": query, "session_id": session_id or thread_id}


# =============================================================================
# LLM MAPPING TEST FUNCTIONS (LOW CONFIDENCE → LLM FALLBACK)
# =============================================================================
# These functions use non-standard naming that should trigger LLM fallback


@endpoint(
    name="test_custom_naming_no_hints",
    description="Test with completely custom parameter names (no mapping hints)",
)
def test_custom_naming_no_hints(xyz: str, abc: str = None, qwerty: dict = None) -> dict:
    """Test LLM fallback with no recognizable patterns.

    Expected: Very low confidence (<0.3), triggers LLM fallback
    xyz, abc, qwerty don't match any standard patterns
    LLM should infer mappings based on description and types
    """
    return {
        "result": xyz,
        "identifier": abc,
        "extras": qwerty,
    }


@endpoint(
    name="test_domain_specific_naming",
    description="Test with domain-specific parameter names for insurance queries",
)
def test_domain_specific_naming(
    insurance_question: str, policy_number: str = None, customer_data: dict = None
) -> dict:
    """Test LLM fallback with domain-specific naming.

    Expected: Low confidence, LLM should map:
    insurance_question → input
    policy_number → session_id (or metadata)
    customer_data → metadata
    """
    return {
        "insurance_answer": f"Answer to: {insurance_question}",
        "policy_number": policy_number,
        "customer_data": customer_data,
    }


@endpoint(
    name="test_abbreviated_names",
    description="Test with abbreviated parameter names",
)
def test_abbreviated_names(q: str, sid: str = None, ctx: List[str] = None) -> dict:
    """Test LLM fallback with abbreviated names.

    Expected: Low-medium confidence
    q → could be query/question (maps to input)
    sid → could be session ID
    ctx → could be context
    LLM should recognize abbreviations
    """
    return {"a": q, "sid": sid, "ctx": ctx}


# =============================================================================
# MANUAL MAPPING TEST FUNCTIONS (CUSTOM @endpoint ANNOTATIONS)
# =============================================================================
# These functions provide explicit mappings via the @endpoint decorator


@endpoint(
    name="test_manual_request_mapping",
    description="Test with manual request mapping annotation",
    request_mapping={
        "user_query": "{{ input }}",
        "session": "{{ session_id }}",
        "docs": "{{ context }}",
    },
)
def test_manual_request_mapping(
    user_query: str, session: str = None, docs: List[str] = None
) -> dict:
    """Test manual request mapping via decorator.

    Expected: Perfect mapping (1.0 confidence)
    Manual mappings take highest priority

    NOTE: This function maps 'context' as an INPUT (not typical, but valid).
    Demonstrates that standard field names can be used flexibly with manual mappings.
    For explicit RAG where frontend retrieves docs and passes them to the function.
    """
    return {
        "response": f"Query: {user_query}",
        "session": session,
        "retrieved_docs": docs,
    }


@endpoint(
    name="test_manual_response_mapping",
    description="Test with manual response mapping annotation",
    response_mapping={
        "output": "$.answer.text",
        "session_id": "$.conversation.id",
        "metadata": "$.conversation.metadata",
    },
)
def test_manual_response_mapping(input: str, session_id: str = None) -> dict:
    """Test manual response mapping via decorator.

    Expected: Response correctly mapped using manual mappings
    Output structure is nested but should be flattened correctly
    """
    return {
        "answer": {"text": f"Response to {input}", "confidence": 0.95},
        "conversation": {
            "id": session_id or "new_session",
            "metadata": {"turns": 1, "topic": "test"},
        },
    }


@endpoint(
    name="test_full_manual_mapping",
    description="Test with both request and response manual mappings",
    request_mapping={
        "customer_message": "{{ input }}",
        "ticket_id": "{{ session_id }}",
        "related_tickets": "{{ context }}",
        "ticket_metadata": "{{ metadata }}",
    },
    response_mapping={
        "output": "$.support_response.message",
        "session_id": "$.support_response.ticket_id",
        "context": "$.support_response.related_info",
        "metadata": "$.support_response.meta",
    },
)
def test_full_manual_mapping(
    customer_message: str,
    ticket_id: str = None,
    related_tickets: List[str] = None,
    ticket_metadata: dict = None,
) -> dict:
    """Test complete manual mapping for both request and response.

    Expected: Perfect end-to-end mapping
    Both request transformation and response transformation work correctly
    """
    return {
        "support_response": {
            "message": f"Thank you for contacting us about: {customer_message}",
            "ticket_id": ticket_id or "TKT-123456",
            "related_info": related_tickets if related_tickets is not None else [],
            "meta": {**{"priority": "high", "department": "support"}, **(ticket_metadata or {})},
        }
    }


# =============================================================================
# COMPLEX OUTPUT STRUCTURE TEST FUNCTIONS
# =============================================================================
# These test different output structures for response mapping


@endpoint(name="test_nested_output", description="Test with deeply nested output structure")
def test_nested_output(input: str) -> dict:
    """Test response mapping with nested output.

    Expected: Auto-mapper should handle nested output field detection
    """
    return {
        "response": {"data": {"result": {"text": f"Nested response to: {input}"}}},
        "session_info": {"id": "nested_session", "created": "2025-01-01"},
    }


@endpoint(name="test_list_output", description="Test with list in output")
def test_list_output(input: str) -> dict:
    """Test response mapping with list outputs."""
    return {
        "results": [
            {"text": f"Result 1 for {input}", "score": 0.9},
            {"text": f"Result 2 for {input}", "score": 0.8},
        ],
        "session_id": "list_session",
    }


@endpoint(name="test_mixed_output_types", description="Test with various output data types")
def test_mixed_output_types(input: str) -> dict:
    """Test response mapping with mixed data types."""
    return {
        "output": f"String output for {input}",
        "confidence": 0.95,  # float
        "tokens_used": 150,  # int
        "success": True,  # bool
        "alternatives": ["alt1", "alt2"],  # list
        "metadata": {"key": "value"},  # dict
    }


# =============================================================================
# CUSTOM FIELD PASSTHROUGH TEST
# =============================================================================


@endpoint(
    name="test_custom_field_passthrough",
    description="Test custom fields passed through request mapping",
    request_mapping={
        "question": "{{ input }}",
        "policy_id": "{{ policy_number }}",  # Custom field
        "tier": "{{ customer_tier }}",  # Custom field
        "lang": "{{ language }}",  # Custom field
    },
    response_mapping={
        "output": "$.answer",
        "session_id": "$.policy_id",
        "metadata": "$.customer_info",
    },
)
def test_custom_field_passthrough(
    question: str, policy_id: str = None, tier: str = "standard", lang: str = "en"
) -> dict:
    """Test that custom fields from API request are passed through correctly.

    Expected behavior:
    - API request includes: input, policy_number, customer_tier, language
    - These map to: question, policy_id, tier, lang
    - Function receives all custom fields correctly

    API Request example:
    {
        "input": "What is my coverage?",
        "policy_number": "POL-123456",
        "customer_tier": "premium",
        "language": "es"
    }
    """
    answer_text = (
        f"[{lang.upper()}] Coverage info for policy {policy_id} (tier: {tier}): {question}"
    )
    return {
        "answer": answer_text,
        "policy_id": policy_id,
        "customer_info": {
            "tier": tier,
            "language": lang,
            "premium_customer": tier in ["premium", "gold"],
        },
    }


# =============================================================================
# ORIGINAL TEST FUNCTIONS
# =============================================================================


@endpoint(name="multiply_numbers", description="Multiply two numbers")
def multiply_numbers(a: int, b: int, c: int) -> dict:
    """Simple multiplication test - should trigger LLM mapping."""
    return {
        "result": a * b * c,
        "error": None,
        "success": True,
        "message": f"The result of {a} * {b} * {c} is {a * b * c}",
    }


@endpoint(
    name="stream_assistant_response", description="Stream assistant responses for insurance queries"
)
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
