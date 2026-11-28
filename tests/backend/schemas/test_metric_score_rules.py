"""The score-field rules a metric must meet to be saved, and the SDK's copy of them.

``check_score_fields`` backs ``MetricCreate`` and ``MetricUpdate``; the SDK's
``GeneratedMetric`` mirrors it so a generated metric always saves. The parity test
below is what keeps the two from drifting apart.
"""

import pytest
from pydantic import ValidationError

from rhesis.backend.app.schemas.metric import MetricCreate, MetricUpdate
from rhesis.backend.app.schemas.metric_types import check_score_fields
from rhesis.sdk.metrics.synthesizer import GeneratedMetric

NUMERIC = {
    "score_type": "numeric",
    "min_score": 0.0,
    "max_score": 1.0,
    "threshold": 0.5,
    "threshold_operator": ">=",
    "categories": None,
    "passing_categories": None,
}
CATEGORICAL = {
    "score_type": "categorical",
    "min_score": None,
    "max_score": None,
    "threshold": None,
    "threshold_operator": None,
    "categories": ["Pass", "Fail"],
    "passing_categories": ["Pass"],
}

VALID = [NUMERIC, CATEGORICAL]
INVALID = [
    {**NUMERIC, "max_score": None},
    {**NUMERIC, "min_score": 1.0, "max_score": 1.0},
    {**NUMERIC, "min_score": 5.0, "max_score": 1.0},
    {**NUMERIC, "threshold": 1.5},
    {**NUMERIC, "threshold": -0.1},
    {**CATEGORICAL, "categories": ["Pass"]},
    {**CATEGORICAL, "passing_categories": []},
    {**CATEGORICAL, "passing_categories": ["pass"]},
]

_TEXT = {
    "name": "Language",
    "description": "Checks the language.",
    "evaluation_prompt": "Judge it.",
    "evaluation_steps": "Step 1:\nRead it.",
    "reasoning": "Quote it.",
    "explanation": "A fail means the wrong language.",
    "metric_scope": ["Single-Turn"],
}


def _score_args(fields: dict) -> dict:
    return {k: v for k, v in fields.items() if k not in ("score_type", "threshold_operator")}


@pytest.mark.unit
class TestCheckScoreFields:
    @pytest.mark.parametrize("fields", VALID)
    def test_a_complete_metric_passes(self, fields):
        check_score_fields(fields["score_type"], **_score_args(fields))

    @pytest.mark.parametrize("fields", INVALID)
    def test_a_metric_the_rules_refuse(self, fields):
        with pytest.raises(ValueError):
            check_score_fields(fields["score_type"], **_score_args(fields))

    def test_an_update_needs_only_what_it_sends(self):
        check_score_fields(
            None,
            min_score=None,
            max_score=None,
            threshold=0.9,
            categories=None,
            passing_categories=None,
            partial=True,
        )

    def test_an_update_that_sends_both_bounds_is_checked(self):
        with pytest.raises(ValueError, match="min_score must be below max_score"):
            check_score_fields(
                None,
                min_score=2.0,
                max_score=1.0,
                threshold=None,
                categories=None,
                passing_categories=None,
                partial=True,
            )


@pytest.mark.unit
class TestSchemasApplyTheRules:
    def test_create_refuses_a_threshold_outside_the_range(self):
        with pytest.raises(ValidationError, match="threshold must lie between"):
            MetricCreate(**_TEXT, **{**NUMERIC, "threshold": 2.0})

    def test_create_refuses_a_passing_category_that_is_not_a_category(self):
        with pytest.raises(ValidationError, match="passing_categories must be among"):
            MetricCreate(**_TEXT, **{**CATEGORICAL, "passing_categories": ["pass"]})

    def test_update_refuses_categories_it_sends_that_do_not_fit(self):
        with pytest.raises(ValidationError, match="passing_categories must be among"):
            MetricUpdate(categories=["Pass", "Fail"], passing_categories=["Maybe"])

    def test_update_of_one_field_is_not_checked_against_the_rest(self):
        assert MetricUpdate(threshold=0.9).threshold == 0.9


@pytest.mark.unit
class TestTheSdkMirrorsTheRules:
    @pytest.mark.parametrize("fields", VALID + INVALID)
    def test_generated_metric_agrees_with_the_save_rules(self, fields):
        try:
            check_score_fields(fields["score_type"], **_score_args(fields))
            saves = True
        except ValueError:
            saves = False
        try:
            GeneratedMetric(**_TEXT, **fields)
            generated = True
        except ValidationError:
            generated = False

        assert generated == saves
