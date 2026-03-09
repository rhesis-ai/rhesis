"""
Tests for Polyphemus Pydantic schemas.

Covers Message, GenerateRequest, and InferenceRequest schema validation,
default values, optional fields, and serialization.
"""

import pytest
from pydantic import ValidationError

from rhesis.polyphemus.schemas import (
    BatchGenerationResponse,
    BatchItemResponse,
    GenerateBatchRequest,
    GenerateRequest,
    GenerationResponse,
    InferenceRequest,
    Message,
)
from rhesis.polyphemus.schemas.schemas import MAX_BATCH_SIZE


class TestMessage:
    def test_valid_message_with_role(self):
        msg = Message(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_valid_message_without_role(self):
        msg = Message(content="Hello!")
        assert msg.role is None
        assert msg.content == "Hello!"

    def test_role_defaults_to_none(self):
        msg = Message(content="test")
        assert msg.role is None

    def test_message_empty_content(self):
        # Empty string is a valid content value (schema does not forbid it)
        msg = Message(content="")
        assert msg.content == ""

    def test_message_system_role(self):
        msg = Message(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"

    def test_message_assistant_role(self):
        msg = Message(role="assistant", content="I can help with that.")
        assert msg.role == "assistant"

    def test_message_serialization_to_dict(self):
        msg = Message(role="user", content="hi")
        d = msg.model_dump()
        assert d == {"role": "user", "content": "hi"}

    def test_message_serialization_without_role(self):
        msg = Message(content="hi")
        d = msg.model_dump()
        assert d == {"role": None, "content": "hi"}

    def test_message_long_content(self):
        long_content = "word " * 5_000  # ~25 k characters
        msg = Message(role="user", content=long_content)
        assert len(msg.content) == len(long_content)

    def test_message_requires_content(self):
        with pytest.raises(ValidationError):
            Message(role="user")  # type: ignore[call-arg]

    def test_message_unicode_content(self):
        msg = Message(role="user", content="こんにちは 🌍 مرحبا")
        assert "🌍" in msg.content


class TestGenerateRequest:
    def test_minimal_request(self):
        req = GenerateRequest(messages=[Message(role="user", content="Hello")])
        assert len(req.messages) == 1
        assert req.model is None
        assert req.max_tokens is None
        assert req.json_schema is None

    def test_default_temperature(self):
        req = GenerateRequest(messages=[Message(content="hi")])
        assert req.temperature == 0.7

    def test_default_stream_is_false(self):
        req = GenerateRequest(messages=[Message(content="hi")])
        assert req.stream is False

    def test_default_repetition_penalty(self):
        req = GenerateRequest(messages=[Message(content="hi")])
        assert req.repetition_penalty == 1.2

    def test_default_top_p_is_none(self):
        req = GenerateRequest(messages=[Message(content="hi")])
        assert req.top_p is None

    def test_default_top_k_is_none(self):
        req = GenerateRequest(messages=[Message(content="hi")])
        assert req.top_k is None

    def test_max_tokens_optional(self):
        req = GenerateRequest(messages=[Message(content="hi")], max_tokens=None)
        assert req.max_tokens is None

    def test_max_tokens_set(self):
        req = GenerateRequest(messages=[Message(content="hi")], max_tokens=1024)
        assert req.max_tokens == 1024

    def test_model_field(self):
        req = GenerateRequest(
            messages=[Message(content="hi")],
            model="polyphemus-default",
        )
        assert req.model == "polyphemus-default"

    def test_full_request_all_fields(self):
        req = GenerateRequest(
            messages=[
                Message(role="system", content="Be concise."),
                Message(role="user", content="Summarise this document."),
            ],
            model="polyphemus-opus",
            temperature=0.5,
            max_tokens=256,
            stream=False,
            repetition_penalty=1.1,
            top_p=0.9,
            top_k=50,
            json_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        )
        assert req.temperature == 0.5
        assert req.max_tokens == 256
        assert req.top_p == 0.9
        assert req.top_k == 50
        assert req.json_schema is not None
        assert len(req.messages) == 2

    def test_multiple_messages(self):
        messages = [Message(role="user", content=f"Turn {i}") for i in range(10)]
        req = GenerateRequest(messages=messages)
        assert len(req.messages) == 10

    def test_json_schema_complex_structure(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "score": {"type": "number"},
            },
            "required": ["name", "score"],
        }
        req = GenerateRequest(
            messages=[Message(content="hi")],
            json_schema=schema,
        )
        assert req.json_schema["type"] == "object"
        assert "name" in req.json_schema["properties"]

    def test_requires_messages(self):
        with pytest.raises(ValidationError):
            GenerateRequest()  # type: ignore[call-arg]

    def test_serialization_round_trip(self):
        req = GenerateRequest(
            messages=[Message(role="user", content="test")],
            temperature=0.9,
            max_tokens=128,
        )
        d = req.model_dump()
        req2 = GenerateRequest.model_validate(d)
        assert req2.temperature == req.temperature
        assert req2.max_tokens == req.max_tokens
        assert req2.messages[0].content == "test"


class TestInferenceRequest:
    def test_default_values(self):
        req = InferenceRequest(prompt="hello")
        assert req.max_tokens == 512
        assert req.temperature == 0.7
        assert req.top_p == 0.9
        assert req.top_k == 50
        assert req.repetition_penalty == 1.1
        assert req.stream is False
        assert req.system_prompt is None

    def test_custom_values(self):
        req = InferenceRequest(
            prompt="Describe the sky.",
            max_tokens=256,
            temperature=0.5,
            top_p=0.8,
            top_k=30,
            repetition_penalty=1.0,
            stream=True,
            system_prompt="Be brief.",
        )
        assert req.prompt == "Describe the sky."
        assert req.max_tokens == 256
        assert req.stream is True
        assert req.system_prompt == "Be brief."

    def test_requires_prompt(self):
        with pytest.raises(ValidationError):
            InferenceRequest()  # type: ignore[call-arg]


class TestGenerationResponse:
    def test_valid_response(self):
        resp = GenerationResponse(
            generated_text="Hello!",
            tokens_generated=5,
            generation_time_seconds=0.42,
        )
        assert resp.generated_text == "Hello!"
        assert resp.tokens_generated == 5
        assert resp.generation_time_seconds == pytest.approx(0.42)

    def test_requires_all_fields(self):
        with pytest.raises(ValidationError):
            GenerationResponse(generated_text="hi")  # type: ignore[call-arg]


class TestGenerateBatchRequest:
    def test_minimal_batch_one_request(self):
        batch = GenerateBatchRequest(
            requests=[GenerateRequest(messages=[Message(role="user", content="Hi")])]
        )
        assert len(batch.requests) == 1
        assert batch.requests[0].messages[0].content == "Hi"

    def test_batch_multiple_requests(self):
        batch = GenerateBatchRequest(
            requests=[
                GenerateRequest(messages=[Message(role="user", content=f"Q{i}")])
                for i in range(5)
            ]
        )
        assert len(batch.requests) == 5

    def test_batch_max_length(self):
        batch = GenerateBatchRequest(
            requests=[
                GenerateRequest(messages=[Message(role="user", content="x")])
                for _ in range(MAX_BATCH_SIZE)
            ]
        )
        assert len(batch.requests) == MAX_BATCH_SIZE

    def test_batch_empty_requests_invalid(self):
        with pytest.raises(ValidationError):
            GenerateBatchRequest(requests=[])  # type: ignore[call-arg]

    def test_batch_over_max_invalid(self):
        with pytest.raises(ValidationError):
            GenerateBatchRequest(
                requests=[
                    GenerateRequest(messages=[Message(role="user", content="x")])
                    for _ in range(MAX_BATCH_SIZE + 1)
                ]
            )

    def test_batch_serialization_round_trip(self):
        batch = GenerateBatchRequest(
            requests=[
                GenerateRequest(messages=[Message(role="user", content="Hello")]),
                GenerateRequest(messages=[Message(role="user", content="World")]),
            ]
        )
        d = batch.model_dump()
        restored = GenerateBatchRequest.model_validate(d)
        assert len(restored.requests) == 2
        assert restored.requests[1].messages[0].content == "World"


class TestBatchItemResponse:
    def test_success_shape(self):
        item = BatchItemResponse(
            choices=[{"message": {"role": "assistant", "content": "Hi"}}],
            model="polyphemus-default",
            usage={"prompt_tokens": 5, "completion_tokens": 10},
        )
        assert item.choices is not None
        assert item.model == "polyphemus-default"
        assert item.usage["completion_tokens"] == 10
        assert item.error is None

    def test_error_shape(self):
        item = BatchItemResponse(error="At least one non-system message with content is required")
        assert item.choices is None
        assert item.model is None
        assert item.usage is None
        assert item.error == "At least one non-system message with content is required"

    def test_all_optional_none(self):
        item = BatchItemResponse()
        assert item.choices is None
        assert item.model is None
        assert item.usage is None
        assert item.error is None


class TestBatchGenerationResponse:
    def test_valid_response(self):
        resp = BatchGenerationResponse(
            responses=[
                BatchItemResponse(
                    choices=[{"message": {"role": "assistant", "content": "A"}}],
                    model="polyphemus-default",
                    usage={"prompt_tokens": 1, "completion_tokens": 1},
                ),
                BatchItemResponse(error="Something went wrong"),
            ]
        )
        assert len(resp.responses) == 2
        assert resp.responses[0].choices is not None
        assert resp.responses[1].error == "Something went wrong"

    def test_requires_responses_list(self):
        with pytest.raises(ValidationError):
            BatchGenerationResponse()  # type: ignore[call-arg]
