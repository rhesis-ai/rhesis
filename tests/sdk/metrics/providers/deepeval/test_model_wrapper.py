"""Tests for DeepEvalModelWrapper._convert_to_schema."""

from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from rhesis.sdk.metrics.providers.deepeval.model import DeepEvalModelWrapper
from rhesis.sdk.models.base import BaseLLM


class FakeVerdict(BaseModel):
    statement: str
    verdict: str
    reason: Optional[str] = Field(default=None)


class FakeVerdicts(BaseModel):
    verdicts: List[FakeVerdict]


@pytest.fixture
def mock_base_llm():
    mock = MagicMock(spec=BaseLLM)
    mock.get_model_name.return_value = "mock-model"
    return mock


@pytest.fixture
def wrapper(mock_base_llm):
    return DeepEvalModelWrapper(mock_base_llm)


class TestConvertToSchema:
    def test_returns_instance_when_result_is_already_correct_type(self, wrapper):
        instance = FakeVerdicts(verdicts=[FakeVerdict(statement="s", verdict="yes")])
        result = wrapper._convert_to_schema(instance, FakeVerdicts)
        assert result is instance

    def test_converts_valid_dict_to_schema_instance(self, wrapper):
        data = {"verdicts": [{"statement": "s", "verdict": "yes", "reason": None}]}
        result = wrapper._convert_to_schema(data, FakeVerdicts)
        assert isinstance(result, FakeVerdicts)
        assert len(result.verdicts) == 1
        assert result.verdicts[0].statement == "s"

    def test_raises_type_error_for_invalid_dict(self, wrapper):
        """When schema instantiation fails, TypeError is raised (not silent dict return)."""
        bad_data = {"wrong_key": "wrong_value"}
        with pytest.raises(TypeError):
            wrapper._convert_to_schema(bad_data, FakeVerdicts)

    def test_raises_type_error_for_non_dict(self, wrapper):
        with pytest.raises(TypeError):
            wrapper._convert_to_schema("not a dict", FakeVerdicts)

    def test_raises_type_error_for_empty_dict(self, wrapper):
        with pytest.raises(TypeError):
            wrapper._convert_to_schema({}, FakeVerdicts)


class TestAGenerate:
    @pytest.mark.asyncio
    async def test_returns_schema_instance_when_model_returns_valid_dict(
        self, wrapper, mock_base_llm
    ):
        valid_dict = {"verdicts": [{"statement": "s", "verdict": "yes", "reason": None}]}
        mock_base_llm.a_generate = AsyncMock(return_value=valid_dict)
        result = await wrapper.a_generate("prompt", schema=FakeVerdicts)
        assert isinstance(result, FakeVerdicts)

    @pytest.mark.asyncio
    async def test_raises_type_error_when_model_returns_wrong_dict(
        self, wrapper, mock_base_llm
    ):
        """TypeError allows deepeval's fallback (unstructured generation) to trigger."""
        mock_base_llm.a_generate = AsyncMock(return_value={"wrong": "data"})
        with pytest.raises(TypeError):
            await wrapper.a_generate("prompt", schema=FakeVerdicts)

    @pytest.mark.asyncio
    async def test_returns_string_when_no_schema(self, wrapper, mock_base_llm):
        mock_base_llm.a_generate = AsyncMock(return_value="raw response")
        result = await wrapper.a_generate("prompt")
        assert result == "raw response"
