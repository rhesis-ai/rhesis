"""Token extraction through the LangChain callback, per provider.

LangChain is the widest surface in the SDK: one callback carries OpenAI, Anthropic,
Gemini, Cohere, Mistral and the rest, and it reads token counts from seven different
places on the response depending on which provider answered. Until now none of that
had a test.

Each case here drives ``extract_and_set_tokens`` with the response shape a real
provider produces and asserts the three span attributes that reach the backend.
"""

from types import SimpleNamespace

import pytest
from rhesis.telemetry.attributes import AIAttributes

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
