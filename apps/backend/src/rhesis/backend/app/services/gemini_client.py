import json
import logging
import os
import random
import re
import time
from typing import AsyncGenerator, Dict, Iterator, List, Union

from google import genai
from google.genai import errors

from rhesis.backend.app.constants import DEFAULT_LANGUAGE_MODEL_NAME

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 10  # seconds


def get_client():
    """Get the Gemini client based on environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Gemini API key not found. Please set GEMINI_API_KEY environment variable."
        )
    return genai.Client(api_key=api_key)


def _get_model_name(client):
    """Get the appropriate model name based on environment variables."""
    return os.getenv("GEMINI_MODEL_NAME", DEFAULT_LANGUAGE_MODEL_NAME)


def _with_retries(func, *args, **kwargs):
    """Execute a function with retry logic for API errors."""
    retries = 0
    while retries <= MAX_RETRIES:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Check if this is an API error that should be retried
            is_api_error = (
                isinstance(e, errors.APIError)
                or "429" in str(e)  # Rate limit
                or "5" in str(e)
                and len(str(e)) >= 3
                and str(e)[0] == "5"  # 5xx error
                or "timeout" in str(e).lower()
                or "connection" in str(e).lower()
            )

            if not is_api_error:
                # If it's not an API error, don't retry
                logger.error(f"Non-retryable error: {str(e)}")
                raise

            retries += 1
            if retries > MAX_RETRIES:
                logger.error(f"Failed after {MAX_RETRIES} retries: {str(e)}")
                raise

            # Calculate exponential backoff with jitter
            delay = min(
                INITIAL_RETRY_DELAY * (2 ** (retries - 1)) + random.uniform(0, 1), MAX_RETRY_DELAY
            )
            logger.warning(
                f"API error: {str(e)}. Retrying in {delay:.2f} seconds (attempt {retries}/{MAX_RETRIES})..."
            )
            time.sleep(delay)


def _sanitize_json_response(text: str) -> str:
    """Remove markdown code block markers and other formatting from JSON responses."""
    if not text:
        return text

    # Check if text starts with ```json - very common pattern
    if text.lstrip().startswith("```json"):
        # Find where the code block ends
        end_marker_pos = text.rfind("```")

        if end_marker_pos > 6:  # Make sure we found the end marker and it's not the start marker
            # Extract the content between markers
            start_content = text.find("\n", text.find("```json")) + 1
            if start_content > 0 and start_content < end_marker_pos:
                return text[start_content:end_marker_pos].strip()

    # Try different patterns for extracting JSON content
    patterns = [
        # Standard markdown code block with or without language specifier
        r"```(?:json)?\s*(.*?)\s*```",
        # Extract content between braces for JSON objects
        r"(\{.*\})",
        # Everything after ```json until the end or next ```
        r"```json\n(.*?)(?:```|$)",
        # Anything after ``` until the end or next ```
        r"```\n(.*?)(?:```|$)",
    ]

    # Try each pattern until one works
    for pattern in patterns:
        try:
            matches = re.search(pattern, text, re.DOTALL)
            if matches:
                extracted = matches.group(1).strip()
                # For JSON object pattern, validate it's actually JSON
                try:
                    json.loads(extracted)
                    return extracted
                except:
                    pass
                return extracted
        except:
            continue

    # If no patterns matched, try simple stripping
    # Match ```json or ``` at the beginning
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    # Match ``` at the end
    text = re.sub(r"\n?```$", "", text)

    return text.strip()


def _adapt_messages_for_gemini(messages: List[Dict[str, str]]):
    """Adapt OpenAI-style messages to Gemini format.

    OpenAI messages have the format: [{"role": "system", "content": "..."}]
    Gemini does not have a native system message concept, so we need to adapt.
    """
    # Extract system messages
    system_messages = [msg["content"] for msg in messages if msg["role"] == "system"]
    system_prompt = "\n".join(system_messages) if system_messages else ""

    # Regular conversation messages
    conversation = [msg for msg in messages if msg["role"] != "system"]

    return system_prompt, conversation


def _create_completion(
    messages,
    response_format=None,
    stream=False,
    model=None,
    temperature=0.7,
    top_p=None,
    n=None,
    max_tokens=None,
    presence_penalty=None,
    frequency_penalty=None,
    raw_response=False,
) -> Union[Dict, Iterator[Dict], str]:
    """Create a chat completion with the given parameters."""
    try:
        client = get_client()
        model_name = model or _get_model_name(client)

        # Process messages for Gemini format
        system_prompt, conversation = _adapt_messages_for_gemini(messages)

        # Create a new chat session with the model
        chat = client.chats.create(model=model_name)

        # Set up JSON format instruction
        json_instruction = ""
        if response_format == "json_object" and not stream:
            json_instruction = """
Your response must be formatted as a valid JSON object.
IMPORTANT: Do NOT include any markdown formatting.
Do NOT include ```json at the beginning or ``` at the end.
Just respond with the raw JSON object by itself.
IMPORTANT: Your entire response must be valid JSON and nothing else.
"""

        # Add system prompt if present
        if system_prompt:
            logger.info(f"Adding system prompt: {system_prompt[:50]}...")
            _with_retries(
                chat.send_message,
                f"System instructions: {system_prompt}\n\nRespond to the user's messages following these instructions.",
            )

        # Add history messages to the chat session
        for i, msg in enumerate(conversation[:-1]):
            if msg["role"] == "user":
                _with_retries(chat.send_message, msg["content"])

        # Add JSON instruction if needed
        if json_instruction:
            _with_retries(chat.send_message, json_instruction)

        # Send the final message and get response
        if stream:
            # Handle streaming
            response_stream = _with_retries(
                chat.send_message_stream, conversation[-1]["content"] if conversation else ""
            )
            return _stream_response(response_stream)
        else:
            # Handle non-streaming
            final_message = conversation[-1]["content"] if conversation else ""
            response = _with_retries(chat.send_message, final_message)

            # Always sanitize JSON responses regardless of raw_response setting
            response_text = response.text
            if response_format == "json_object":
                response_text = _sanitize_json_response(response.text)

            # Format according to raw_response setting
            if raw_response:
                return {"choices": [{"message": {"content": response_text}}]}
            else:
                return response_text

    except Exception as e:
        logger.error(f"Error getting Gemini response: {str(e)}")
        if stream:
            # For streaming errors, return a generator that yields an error message
            def _error_stream():
                yield {
                    "choices": [
                        {
                            "delta": {
                                "content": f"I apologize, but I couldn't process your request due to an error: {str(e)}"
                            }
                        }
                    ]
                }

            return _error_stream()
        raise


def _stream_response(response_stream):
    """Convert Gemini streaming response to OpenAI-compatible format."""
    for chunk in response_stream:
        if chunk.text:
            # Create a response object similar to OpenAI's streaming format
            yield {"choices": [{"delta": {"content": chunk.text}}]}


def get_json_response(prompt: str, stream: bool = False) -> Union[dict, AsyncGenerator[str, None]]:
    """Get a JSON response from Gemini API."""
    try:
        messages = [
            {
                "role": "system",
                "content": """You are a helpful assistant that always responds in valid JSON format.
Your entire response must be a single valid JSON object.
IMPORTANT: Do NOT include any markdown formatting.
Do NOT include ```json at the beginning or ``` at the end.
Just respond with the raw JSON object by itself.
IMPORTANT: Your entire response must be valid JSON and nothing else.""",
            },
            {"role": "user", "content": prompt},
        ]

        response = _create_completion(
            messages=messages,
            response_format="json_object",
            stream=stream,
            temperature=0.7,
        )

        if not stream:
            # Parse the response as JSON
            try:
                if not response or not isinstance(response, str):
                    logger.error(f"Received invalid response format: {type(response)}")
                    return {"error": "Received empty or invalid response from model"}

                # The response should already be sanitized by _create_completion
                return json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {str(e)}")
                return {"error": "Failed to parse model response as JSON"}

            except Exception as e:
                logger.error(f"Error processing JSON response: {str(e)}")
                return {"error": str(e)}
        else:
            # For streaming, return chunks compatible with OpenAI's format
            async def _stream_json_response():
                for chunk in response:
                    if chunk["choices"][0]["delta"]["content"]:
                        yield chunk["choices"][0]["delta"]["content"]

            return _stream_json_response()

    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        if stream:

            async def _error_response():
                yield json.dumps({"error": str(e)})

            return _error_response()
        return {"error": str(e)}  # Return error as JSON object instead of raising


def get_chat_response(
    messages,
    response_format="json_object",
    stream=False,
    model=None,
    temperature=0.7,
    top_p=None,
    n=None,
    max_tokens=None,
    presence_penalty=None,
    frequency_penalty=None,
    raw_response=False,
):
    """Get response from Gemini API using a messages array."""
    response = _create_completion(
        messages=messages,
        response_format=response_format if response_format != "text" and not stream else None,
        stream=stream,
        model=model,
        temperature=temperature,
        top_p=top_p,
        n=n,
        max_tokens=max_tokens,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        raw_response=raw_response,
    )

    if stream:
        return response

    if raw_response:
        return response

    # If we get here, response should already be sanitized text
    if response_format == "json_object":
        try:
            if not response or not isinstance(response, str):
                logger.error(f"Received invalid response format: {type(response)}")
                return {"error": "Received empty or invalid response from model"}

            # Try to parse the sanitized JSON
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON response")
            return {"error": "Failed to parse model response as JSON"}
    else:
        return response


def create_chat_completion(request: dict):
    """Create a chat completion using Gemini API."""
    try:
        # Extract standard parameters
        messages = request["messages"]
        stream = request.get("stream", False)

        # Optional parameters
        model = request.get("model")
        temperature = request.get("temperature")
        top_p = request.get("top_p")
        n = request.get("n")
        max_tokens = request.get("max_tokens")
        presence_penalty = request.get("presence_penalty")
        frequency_penalty = request.get("frequency_penalty")
        response_format = request.get("response_format")

        # Build kwargs with only the parameters that are not None
        kwargs = {
            "messages": messages,
            **({"model": model} if model is not None else {}),
            **({"temperature": temperature} if temperature is not None else {}),
            **({"top_p": top_p} if top_p is not None else {}),
            **({"n": n} if n is not None else {}),
            **({"max_tokens": max_tokens} if max_tokens is not None else {}),
            **({"presence_penalty": presence_penalty} if presence_penalty is not None else {}),
            **({"frequency_penalty": frequency_penalty} if frequency_penalty is not None else {}),
            **({"response_format": response_format} if response_format is not None else {}),
            "raw_response": True,  # Always get raw response for this endpoint
        }

        return get_chat_response(**kwargs, stream=stream)
    except Exception as e:
        logger.error(f"Error in create_chat_completion: {str(e)}")
        error_msg = str(e)
        if stream:
            # For streaming errors, return a generator that yields an error message
            def _error_stream():
                yield {"choices": [{"delta": {"content": f"Error: {error_msg}"}}]}

            return _error_stream()
        else:
            # For non-streaming, return an error object
            return {"choices": [{"message": {"content": f"Error: {error_msg}"}}]}
