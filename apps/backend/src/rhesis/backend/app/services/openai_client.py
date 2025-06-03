import json
import os
from typing import AsyncGenerator, Iterator, Union

from openai import AzureOpenAI, OpenAI

# Think about https://pypi.org/project/json-repair/ to enable JSON parsing 
# of OpenAI responses in stream mode


def get_client():
    """Get the appropriate OpenAI client based on environment variables."""
    if os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY"):
        return AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
    elif os.getenv("OPENAI_API_KEY"):
        return OpenAI()
    else:
        raise EnvironmentError(
            "Neither OpenAI nor Azure OpenAI credentials found. "
            "Please set either OPENAI_API_KEY or both AZURE_OPENAI_ENDPOINT and "
            "AZURE_OPENAI_API_KEY"
        )


def _get_model_name(client):
    """Get the appropriate model name based on client type."""
    model = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

    if isinstance(client, AzureOpenAI):
        model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not model:
            raise EnvironmentError(
                "AZURE_OPENAI_DEPLOYMENT_NAME environment variable is required for Azure OpenAI"
            )
    return model


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
) -> Union[str, Iterator[str]]:
    """Create a chat completion with the given parameters."""
    client = get_client()
    model = model or _get_model_name(client)

    params = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": temperature,
        **({"top_p": top_p} if top_p is not None else {}),
        **({"n": n} if n is not None else {}),
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        **({"presence_penalty": presence_penalty} if presence_penalty is not None else {}),
        **({"frequency_penalty": frequency_penalty} if frequency_penalty is not None else {}),
    }

    if response_format and not stream:  # response_format not supported with streaming
        params["response_format"] = {"type": response_format}

    try:
        response = client.chat.completions.create(**params)

        if stream:
            return _stream_response(response)
        return response if raw_response else response.choices[0].message.content
    except Exception as e:
        print(f"Error getting OpenAI response: {str(e)}")
        raise


def _stream_response(response) -> Iterator[str]:
    """Handle streaming response from OpenAI API."""
    for chunk in response:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


def get_json_response(prompt: str, stream: bool = False) -> Union[dict, AsyncGenerator[str, None]]:
    """Get a JSON response from OpenAI API."""
    try:
        client = get_client()
        model = _get_model_name(client)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that always responds in valid "
                              "JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            stream=stream,
        )

        if not stream:
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                # Ensure the content is valid JSON
                return json.loads(content)
            raise ValueError("No response content received from OpenAI")
        else:

            async def _stream_response():
                async for chunk in response:
                    if (
                        chunk.choices
                        and len(chunk.choices) > 0
                        and chunk.choices[0].delta
                        and chunk.choices[0].delta.content
                    ):
                        yield chunk.choices[0].delta.content

            return _stream_response()
    except Exception as e:
        print(f"OpenAI API error: {str(e)}")
        raise e


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
    """Get response from OpenAI API using a messages array.

    Args:
        messages: List of message objects with role and content
        response_format: The format to return ("json_object" or "text")
        stream: Whether to stream the response
        model: The model to use (defaults to environment variable)
        temperature: Sampling temperature (0-2)
        top_p: Nucleus sampling parameter (0-1)
        n: Number of completions to generate
        max_tokens: Maximum tokens in the response
        presence_penalty: Presence penalty (-2.0 to 2.0)
        frequency_penalty: Frequency penalty (-2.0 to 2.0)
        raw_response: Whether to return the raw OpenAI response object

    Returns:
        The response from OpenAI API in the specified format,
        or an iterator of response chunks if streaming
    """
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

    return json.loads(response) if response_format == "json_object" else response


def create_chat_completion(request: dict):
    """Create a chat completion using OpenAI API.

    Args:
        request: The complete chat completion request body matching OpenAI's format

    Returns:
        Union[dict, Iterator[str]]: The OpenAI API response or a stream of response chunks
    """
    try:
        # Extract standard OpenAI parameters
        messages = request["messages"]
        stream = request.get("stream", False)

        # Optional parameters that OpenAI accepts
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
        print(f"Error in create_chat_completion: {str(e)}")
        raise
