"""Token extraction through the LangChain callback, per provider.

LangChain is the widest surface in the SDK: one callback carries OpenAI, Anthropic,
Gemini, Cohere, Mistral and the rest, and it reads token counts from seven different
places on the response depending on which provider answered. Until now none of that
had a test.

Each case here drives ``extract_and_set_tokens`` with the response shape a real
provider produces and asserts the three span attributes that reach the backend.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from rhesis.telemetry.attributes import AIAttributes

from rhesis.sdk.telemetry.integrations.langchain.callback import create_langchain_callback
from rhesis.sdk.telemetry.integrations.langchain.llm_processing import extract_and_set_tokens


class RecordingSpan:
    """Captures set_attribute calls. The callback only ever writes, never reads."""

    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, *args, **kwargs):
        pass

    def is_recording(self):
        return True


def tokens_on(span):
    return (
        span.attributes.get(AIAttributes.LLM_TOKENS_INPUT),
        span.attributes.get(AIAttributes.LLM_TOKENS_OUTPUT),
        span.attributes.get(AIAttributes.LLM_TOKENS_TOTAL),
    )


def result(llm_output=None, generations=None, usage=None):
    """Stand-in for LangChain's LLMResult, carrying only what the extractor reads."""
    response = SimpleNamespace(
        llm_output=llm_output,
        generations=generations if generations is not None else [],
    )
    if usage is not None:
        response.usage = usage
    return response


class TestTokenSources:
    """The seven places a provider can put its counts."""

    def test_source_1_openai_style_llm_output(self):
        span = RecordingSpan()

        extract_and_set_tokens(
            span,
            result(
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    }
                }
            ),
        )

        assert tokens_on(span) == (10, 20, 30)

    def test_source_2_anthropic_style_llm_output(self):
        span = RecordingSpan()

        extract_and_set_tokens(
            span,
            result(llm_output={"usage": {"input_tokens": 50, "output_tokens": 20}}),
        )

        assert tokens_on(span) == (50, 20, 70)

    def test_source_3_usage_object_keeps_anthropic_cache_tokens(self):
        """The regression this path used to have.

        It pre-flattened the usage object through its own short list of attribute
        names, one that omitted the two cache fields, so a cached Anthropic call
        reached the span reporting 70 tokens instead of 5070. The shared extractor
        had already been fixed; this copy undid it.
        """
        from anthropic.types import Usage

        span = RecordingSpan()

        extract_and_set_tokens(
            span,
            result(
                usage=Usage(
                    input_tokens=50,
                    output_tokens=20,
                    cache_creation_input_tokens=1000,
                    cache_read_input_tokens=4000,
                )
            ),
        )

        assert tokens_on(span) == (50, 20, 5070)

    def test_source_4_message_usage_metadata(self):
        span = RecordingSpan()
        message = SimpleNamespace(
            usage_metadata={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
            response_metadata={},
        )

        extract_and_set_tokens(
            span, result(generations=[[SimpleNamespace(message=message, generation_info=None)]])
        )

        assert tokens_on(span) == (12, 8, 20)

    def test_source_5_message_response_metadata(self):
        span = RecordingSpan()
        message = SimpleNamespace(
            usage_metadata=None,
            response_metadata={
                "token_usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11}
            },
        )

        extract_and_set_tokens(
            span, result(generations=[[SimpleNamespace(message=message, generation_info=None)]])
        )

        assert tokens_on(span) == (5, 6, 11)

    def test_source_7_generation_info(self):
        span = RecordingSpan()
        generation = SimpleNamespace(
            message=None,
            generation_info={
                "usage_metadata": {"prompt_token_count": 15, "candidates_token_count": 25}
            },
        )

        extract_and_set_tokens(span, result(generations=[[generation]]))

        assert tokens_on(span) == (15, 25, 40)


class TestPerProvider:
    """The usage payload each provider's LangChain integration actually hands over."""

    @pytest.mark.parametrize(
        ("name", "llm_output", "expected"),
        [
            (
                "openai",
                {"token_usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}},
                (10, 20, 30),
            ),
            (
                "anthropic",
                {"usage": {"input_tokens": 50, "output_tokens": 20}},
                (50, 20, 70),
            ),
            (
                "gemini",
                {"token_usage": {"prompt_token_count": 15, "candidates_token_count": 25}},
                (15, 25, 40),
            ),
            (
                "mistral",
                {"token_usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33}},
                (11, 22, 33),
            ),
            (
                "cohere",
                {"token_usage": {"billed_units": {"input_tokens": 7, "output_tokens": 3}}},
                (7, 3, 10),
            ),
        ],
    )
    def test_provider_payload_reaches_the_span(self, name, llm_output, expected):
        span = RecordingSpan()

        extract_and_set_tokens(span, result(llm_output=llm_output))

        assert tokens_on(span) == expected, f"{name} tokens did not survive"


class TestNothingToReport:
    def test_a_response_with_no_usage_sets_no_token_attributes(self):
        """Absent is not zero: writing zeros would claim the call used nothing."""
        span = RecordingSpan()

        extract_and_set_tokens(span, result(llm_output={}))

        assert tokens_on(span) == (None, None, None)


def cache_tokens_on(span):
    return (
        span.attributes.get(AIAttributes.LLM_TOKENS_CACHE_WRITE),
        span.attributes.get(AIAttributes.LLM_TOKENS_CACHE_READ),
    )


class TestCacheTokens:
    """Cached prompt tokens reach the span so the backend can price them.

    They are counted in the total but billed at their own rates, so recording only the
    total left a cached call costed as though it had not used the cache.
    """

    def test_they_are_recorded_from_a_usage_object(self):
        from anthropic.types import Usage

        span = RecordingSpan()

        extract_and_set_tokens(
            span,
            result(
                usage=Usage(
                    input_tokens=50,
                    output_tokens=20,
                    cache_creation_input_tokens=1000,
                    cache_read_input_tokens=4000,
                )
            ),
        )

        assert cache_tokens_on(span) == (1000, 4000)
        # And the three ordinary counts still add up with them.
        assert tokens_on(span) == (50, 20, 5070)

    def test_they_are_recorded_from_llm_output(self):
        span = RecordingSpan()

        extract_and_set_tokens(
            span,
            result(
                llm_output={
                    "usage": {
                        "input_tokens": 50,
                        "output_tokens": 20,
                        "cache_read_input_tokens": 4000,
                    }
                }
            ),
        )

        assert cache_tokens_on(span) == (None, 4000)

    def test_they_are_recorded_from_message_metadata(self):
        span = RecordingSpan()
        message = SimpleNamespace(
            usage_metadata={
                "input_tokens": 12,
                "output_tokens": 8,
                "cache_creation_input_tokens": 300,
            },
            response_metadata={},
        )

        extract_and_set_tokens(
            span, result(generations=[[SimpleNamespace(message=message, generation_info=None)]])
        )

        assert cache_tokens_on(span) == (300, None)

    def test_a_call_that_used_no_cache_records_neither(self):
        """Absent, not zero, so the attributes stay off the overwhelming majority."""
        span = RecordingSpan()

        extract_and_set_tokens(
            span,
            result(
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    }
                }
            ),
        )

        assert cache_tokens_on(span) == (None, None)


# Wire shapes for one cached call per provider. OpenAI: 1000 prompt tokens, 800 of them
# from cache. Anthropic: 50 fresh, 1000 written to cache, 4000 read from it.
OPENAI_USAGE = {
    "prompt_tokens": 1000,
    "completion_tokens": 20,
    "total_tokens": 1020,
    "prompt_tokens_details": {"cached_tokens": 800, "audio_tokens": 0},
    "completion_tokens_details": {"reasoning_tokens": 0, "audio_tokens": 0},
}
ANTHROPIC_USAGE = {
    "input_tokens": 50,
    "output_tokens": 20,
    "cache_creation_input_tokens": 1000,
    "cache_read_input_tokens": 4000,
}
# A Messages response also splits writes by TTL; the streamed message_delta does not.
ANTHROPIC_RESPONSE_USAGE = {
    **ANTHROPIC_USAGE,
    "cache_creation": {"ephemeral_5m_input_tokens": 1000, "ephemeral_1h_input_tokens": 0},
}


def openai_reply(body):
    head = {"id": "chatcmpl-1", "created": 0, "model": "gpt-4o-mini"}
    if not body.get("stream"):
        message = {"role": "assistant", "content": "Hello"}
        choice = {"index": 0, "message": message, "finish_reason": "stop"}
        return {**head, "object": "chat.completion", "choices": [choice], "usage": OPENAI_USAGE}
    chunk = {**head, "object": "chat.completion.chunk"}
    delta = {"role": "assistant", "content": "Hello"}
    return [
        (None, {**chunk, "choices": [{"index": 0, "delta": delta}]}),
        (None, {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}),
        # stream_options.include_usage: a last chunk with no choices, carrying the usage.
        (None, {**chunk, "choices": [], "usage": OPENAI_USAGE}),
    ]


def anthropic_reply(body):
    message = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "stop_reason": "end_turn",
        "stop_sequence": None,
    }
    text = {"type": "text", "text": "Hello"}
    if not body.get("stream"):
        return {**message, "content": [text], "usage": ANTHROPIC_RESPONSE_USAGE}
    started = {**message, "content": [], "stop_reason": None, "usage": ANTHROPIC_RESPONSE_USAGE}
    finished = {"stop_reason": "end_turn", "stop_sequence": None}
    return [
        ("message_start", {"type": "message_start", "message": started}),
        ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": text}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        # message_delta's usage is cumulative, input and cache counts included.
        ("message_delta", {"type": "message_delta", "delta": finished, "usage": ANTHROPIC_USAGE}),
        ("message_stop", {"type": "message_stop"}),
    ]


@pytest.fixture(scope="module")
def provider_url():
    """A local stand-in for the OpenAI and Anthropic APIs, so the real clients parse it."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            reply = (openai_reply if self.path.endswith("/chat/completions") else anthropic_reply)(
                body
            )
            if isinstance(reply, dict):
                payload, content_type = json.dumps(reply), "application/json"
            else:
                payload = "".join(
                    (f"event: {name}\n" if name else "") + f"data: {json.dumps(data)}\n\n"
                    for name, data in reply
                )
                if reply[0][0] is None:  # OpenAI ends its stream with a sentinel
                    payload += "data: [DONE]\n\n"
                content_type = "text/event-stream"
            encoded = payload.encode()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def chat_model(provider, url):
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o-mini", api_key="test", base_url=f"{url}/v1", stream_usage=True
        )
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model="claude-sonnet-5-5", api_key="test", anthropic_api_url=url, max_tokens=1024
    )


def recorded_tokens(model, mode):
    """Run one call through the Rhesis callback and return its LLM span's token attributes."""
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    callback = create_langchain_callback()
    callback.tracer = tracer_provider.get_tracer("test")
    config = {"callbacks": [callback]}

    if mode == "invoke":
        model.invoke("hi", config=config)
    else:
        for _ in model.stream("hi", config=config):
            pass

    [span] = [s for s in exporter.get_finished_spans() if s.name == "ai.llm.invoke"]
    return {
        key: span.attributes.get(key)
        for key in (
            AIAttributes.LLM_TOKENS_INPUT,
            AIAttributes.LLM_TOKENS_OUTPUT,
            AIAttributes.LLM_TOKENS_TOTAL,
            AIAttributes.LLM_TOKENS_CACHE_WRITE,
            AIAttributes.LLM_TOKENS_CACHE_READ,
        )
    }


class TestStreamedCallsKeepTheirCacheTokens:
    """A streamed call carries its usage only on usage_metadata, cache counts included.

    Reading input_tokens there without taking the cache out priced every cached token
    at the full input rate. The same response must record the same counts whichever
    way it was called.
    """

    EXPECTED = {
        "openai": (200, 20, 1020, None, 800),
        "anthropic": (50, 20, 5070, 1000, 4000),
    }

    @pytest.mark.parametrize("provider", ["openai", "anthropic"])
    @pytest.mark.parametrize("mode", ["invoke", "stream"])
    def test_cached_tokens_are_recorded(self, provider_url, provider, mode):
        tokens = recorded_tokens(chat_model(provider, provider_url), mode)

        assert tuple(tokens.values()) == self.EXPECTED[provider]

    @pytest.mark.parametrize("provider", ["openai", "anthropic"])
    def test_invoke_and_stream_record_the_same_attributes(self, provider_url, provider):
        model = chat_model(provider, provider_url)

        assert recorded_tokens(model, "invoke") == recorded_tokens(model, "stream")

    def test_anthropic_writes_split_by_ttl_are_read_from_usage_metadata(self, provider_url):
        """A reply's usage_metadata reports writes per TTL and cache_creation as 0."""
        message = chat_model("anthropic", provider_url).invoke("hi")
        details = message.usage_metadata["input_token_details"]
        assert (details["cache_creation"], details["ephemeral_5m_input_tokens"]) == (0, 1000)
        span = RecordingSpan()

        extract_and_set_tokens(
            span, result(generations=[[SimpleNamespace(message=message, generation_info=None)]])
        )

        assert tokens_on(span) == (50, 20, 5070)
        assert cache_tokens_on(span) == (1000, 4000)
