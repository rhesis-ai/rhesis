"""Generation config field names are canonical, aliased, and closed to typos.

These fields are lists, so the plural names match the SDK's `GenerationConfig`
exactly and the config dict is built by copying them straight across. A name that
does not line up used to be dropped by pydantic's default `extra="ignore"`, leaving
`requirements` as `None`, which sends the multi-turn generation prompt down its
default branch — so generation ran against the seeded default requirements
(Compliance / Reliability / Robustness) instead of the ones requested, and nothing
raised.

`requirements` being required on `GenerationConfig` already made a typo there loud,
but every field on `GenerateMultiTurnTestsRequest` is optional, and `categories` and
`topics` are optional on both. Those were silently ignored.

The older singular spellings stay accepted as aliases so existing clients keep
working.
"""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.services import (
    GenerateMultiTurnTestsRequest,
    GenerationConfig,
)


@pytest.mark.unit
class TestGenerateMultiTurnTestsRequest:
    def test_plural_names_are_canonical(self):
        request = GenerateMultiTurnTestsRequest(
            generation_prompt="x",
            requirements=["Summary Grounding"],
            categories=["Harmless"],
            topics=["triage"],
        )

        assert request.requirements == ["Summary Grounding"]
        assert request.categories == ["Harmless"]
        assert request.topics == ["triage"]

    def test_singular_spellings_are_accepted_as_aliases(self):
        """The pre-existing shape. Dropping it would break existing API clients."""
        request = GenerateMultiTurnTestsRequest(
            generation_prompt="x",
            requirement=["Summary Grounding"],
            category=["Harmless"],
            topic=["triage"],
        )

        assert request.requirements == ["Summary Grounding"]
        assert request.categories == ["Harmless"]
        assert request.topics == ["triage"]

    @pytest.mark.parametrize("field", ["requirementz", "categoriez", "topicz", "nonsense"])
    def test_unknown_field_raises_rather_than_being_dropped(self, field):
        with pytest.raises(ValidationError):
            GenerateMultiTurnTestsRequest(generation_prompt="x", **{field: ["A"]})


@pytest.mark.unit
class TestGenerationConfig:
    def test_singular_requirement_is_accepted_as_an_alias(self):
        config = GenerationConfig(generation_prompt="x", requirement=["Summary Grounding"])

        assert config.requirements == ["Summary Grounding"]

    def test_model_dump_uses_the_canonical_plural_names(self):
        """The job hands this dict to the SDK config, which forbids unknown keys, so a
        dump that emitted the singular aliases would fail there instead."""
        config = GenerationConfig(generation_prompt="x", requirement=["A"])

        assert set(config.model_dump()) == {
            "generation_prompt",
            "requirements",
            "categories",
            "topics",
            "additional_context",
        }

    def test_requirements_is_still_required(self):
        with pytest.raises(ValidationError):
            GenerationConfig(generation_prompt="x")

    def test_empty_requirements_is_rejected(self):
        with pytest.raises(ValidationError):
            GenerationConfig(generation_prompt="x", requirements=[])

    @pytest.mark.parametrize("field", ["requirementz", "categoriez", "topicz"])
    def test_unknown_field_raises_rather_than_being_dropped(self, field):
        with pytest.raises(ValidationError):
            GenerationConfig(generation_prompt="x", requirements=["A"], **{field: ["B"]})
